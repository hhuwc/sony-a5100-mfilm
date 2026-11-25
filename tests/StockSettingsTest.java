package org.mfilm.sony;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class StockSettingsTest {
    static final class Body implements StockSettings.Body {
        final Map<String,String> state=new HashMap<String,String>();
        final List<String> notes=new ArrayList<String>();
        String reject,ignore;
        int writes,monoSaturationWrites;
        Body(){
            state.put("storage-fmt","jpeg");state.put("iso-sensitivity","auto");
            state.put("iso-sensitivity-values","auto,100,125,160,200,400,800,1600,3200");
            state.put("whitebalance","auto");state.put("whitebalance-values","auto, color-temp");
            state.put(StockSettings.KELVIN,"5500");
            state.put("color-mode","portrait");state.put("color-mode-values","portrait,mono,standard,landscape");
            for(String key:new String[]{"contrast","saturation","sharpness",StockSettings.AB,StockSettings.GM}){
                state.put(key,key.endsWith("white-balance")?"1":"0");
                state.put("min-"+key,"-3");state.put("max-"+key,"3");
            }
            state.put("focus-mode","auto");state.put("exposure-compensation","2");
        }
        public StockSettings.Values read(){
            final Map<String,String> snapshot=new HashMap<String,String>(state);
            return new StockSettings.Values(){public String get(String key){return snapshot.get(key);}};
        }
        public void write(Map<String,String> changes,boolean capture){
            require(!changes.isEmpty(),"empty write");
            require(!changes.containsKey("focus-mode") && !changes.containsKey("exposure-compensation"),"AF or EV changed");
            if(reject!=null && changes.containsKey(reject))throw new IllegalStateException("rejected "+reject);
            if(changes.containsKey("whitebalance")){
                require(capture && changes.containsKey(StockSettings.KELVIN),"temperature missing at mode switch");
                state.put(StockSettings.KELVIN,"4300");
            }
            if(changes.containsKey("color-mode") && !"color-mode".equals(ignore)){
                require(!capture && changes.size()==1,"style must precede adjustments");
                state.put("contrast","-3");state.put("saturation","-3");state.put("sharpness","3");
            }
            if("mono".equals(state.get("color-mode")) && changes.containsKey("saturation"))monoSaturationWrites++;
            for(Map.Entry<String,String> e:changes.entrySet())if(!e.getKey().equals(ignore))state.put(e.getKey(),e.getValue());
            writes++;
        }
        public void note(String s){notes.add(s);}
        void is(String key,Object expected){require(String.valueOf(expected).equals(state.get(key)),key+" expected "+expected+" got "+state.get(key));}
    }
    static void require(boolean pass,String msg){if(!pass)throw new AssertionError(msg);}

    public static void main(String[] args)throws Exception{
        int count=0,mono=0,landscape=0,standard=0,rounded=0;
        StockSettings session=new StockSettings();
        Body body=new Body();
        try(BufferedReader lines=new BufferedReader(new FileReader(args[0]))){
            for(String row;(row=lines.readLine())!=null;){
                String[] cells=row.split("\t");
                require(cells.length==10,row);
                int[] film=new int[8];
                for(int i=0;i<film.length;i++)film[i]=Integer.parseInt(cells[i+2]);
                int box=Integer.parseInt(cells[1]),iso=100;
                while(iso<box)iso*=2;
                if(box==125 || box==160)rounded++;
                require(iso==film[0],cells[0]+": capture ISO");
                session.apply(body,film);
                body.is("iso-sensitivity",iso);
                body.is("storage-fmt","rawjpeg");body.is("whitebalance","color-temp");
                body.is(StockSettings.KELVIN,cells[0].equals("cinestill800t")?3200:5500);
                body.is(StockSettings.AB,0);body.is(StockSettings.GM,0);
                body.is("contrast",Math.min(3,film[3]));
                body.is("sharpness",film[5]-3);
                if(film[2]==0x86){body.is("color-mode","mono");mono++;}
                else{
                    String style=film[2]==0x83?"landscape":"standard";
                    body.is("color-mode",style);body.is("saturation",Math.min(3,film[4]));
                    if(film[2]==0x83)landscape++;else standard++;
                }
                int writes=body.writes;
                session.apply(body,film);
                require(body.writes==writes,"duplicate writes on reapply "+cells[0]);
                count++;
            }
        }
        require(count==68 && standard==26 && landscape==20 && mono==22 && rounded==5,"catalogue totals");
        require(body.notes.isEmpty() && body.monoSaturationWrites==0,"normal set/readback");
        body.is("focus-mode","auto");body.is("exposure-compensation",2);
        body.state.put(StockSettings.GM,"-2"); // changed separately after Film OS applied its settings
        session.restoreShift(body);body.is(StockSettings.AB,1);body.is(StockSettings.GM,-2);
        int settled=body.writes;
        session.restoreShift(body);require(settled==body.writes,"repeat release");
        System.out.println(count+" catalogue stocks: "+standard+" Standard, "+landscape+" Landscape, "+mono+" B&W; "+rounded+" whole-stop ISO conversions");

        int[] film={400,5500,0x81,1,1,2,0,0};
        Body failed=new Body();failed.reject="color-mode";
        session.apply(failed,film);
        failed.is("storage-fmt","rawjpeg");failed.is("iso-sensitivity",400);
        failed.is(StockSettings.AB,0);failed.is("color-mode","portrait");failed.is("contrast",0);
        require(!failed.notes.isEmpty(),"driver rejection not reported");
        session.restoreShift(failed);failed.is(StockSettings.AB,1);
        Body ignored=new Body();ignored.ignore="color-mode";
        session.apply(ignored,film);ignored.is("contrast",0);
        require(!ignored.notes.isEmpty(),"ignored style not reported");
        session.restoreShift(ignored);
        Body missing=new Body();
        missing.state.put("storage-fmt","raw");
        missing.state.remove("min-saturation");missing.state.put("max-contrast","invalid");
        missing.state.remove(StockSettings.AB);missing.state.remove("color-mode-values");
        session.apply(missing,film);missing.is("storage-fmt","raw");missing.is("color-mode","portrait");
        missing.state.put("color-mode","standard");
        session.apply(missing,film);missing.is("saturation",0);missing.is("contrast",0);missing.is("sharpness",-1);
        session.restoreShift(missing);missing.is(StockSettings.GM,1);
        Body wide=new Body();wide.state.put("max-saturation","8");wide.state.put("max-contrast","1");
        session.apply(wide,new int[]{100,5500,0x83,3,4,3,0,0});
        wide.is("contrast",1);wide.is("saturation",3);session.restoreShift(wide);
        Body different=new Body();int[] shifted={400,3200,0x81,0,0,3,2,1};
        session.apply(different,shifted);different.is(StockSettings.AB,2);different.is(StockSettings.GM,-1);
        different.ignore=StockSettings.AB;session.restoreShift(different);different.is(StockSettings.AB,2);
        different.ignore=null;session.restoreShift(different);different.is(StockSettings.AB,1);
        System.out.println("Passed WB restore/retry/external edit, colour to mono, unsupported ranges and style, write rejection and ignored writes. AF and EV preserved.");
    }
}

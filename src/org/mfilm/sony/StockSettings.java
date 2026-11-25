package org.mfilm.sony;

import java.util.LinkedHashMap;
import java.util.Map;

/** Film OS sets a stock's capture balance and its preview style separately from RAW development. */
final class StockSettings {
    interface Values { String get(String key); }
    interface Body {
        Values read();
        void write(Map<String,String> changes,boolean capture) throws Exception;
        void note(String message);
    }

    static final String AB="light-balance-for-white-balance", GM="color-compensation-for-white-balance";
    static final String KELVIN="color-temperture-white-balance"; // Sony's spelling
    private final Map<String,String> originalShift=new LinkedHashMap<String,String>();
    private final Map<String,String> lastShift=new LinkedHashMap<String,String>();

    private static boolean supports(Values v,String key,String choice){
        String choices=v.get(key+"-values");
        if(choices!=null)for(String item:choices.split(","))if(choice.equals(item.trim()))return true;
        return false;
    }

    private static void set(Map<String,String> changes,Values v,String key,String value){
        String current=v.get(key);
        if(current!=null && !current.equals(value))changes.put(key,value);
    }

    private static void level(Map<String,String> changes,Values v,String key,int value){
        if(v.get(key)==null)return;
        // Only use the range that the current mode advertises.
        try{
            int low=Integer.parseInt(v.get("min-"+key)),high=Integer.parseInt(v.get("max-"+key));
            if(low<=high)set(changes,v,key,String.valueOf(Math.max(low,Math.min(high,value))));
        }catch(NumberFormatException unavailable){}
    }
    private static int styleLevel(int value){return Math.max(-3,Math.min(3,value));}

    private static Values commit(Body body,Values current,Map<String,String> changes,String group,boolean capture){
        if(changes.isEmpty())return current;
        try{body.write(changes,capture);}
        catch(Exception e){body.note(group+" write: "+e);}
        Values actual=body.read();
        for(Map.Entry<String,String> entry:changes.entrySet()){
            String seen=actual.get(entry.getKey());
            if(!entry.getValue().equals(seen))body.note(group+" requested "+entry+", read back "+seen);
        }
        return actual;
    }

    /** Native fields: EOS M capture ISO, Kelvin, Picture Style, contrast, saturation, sharpness, AB and GM. */
    void apply(Body body,int[] film){
        Values v=body.read();
        Map<String,String> changes=new LinkedHashMap<String,String>();
        String format=v.get("storage-fmt");
        if(!"raw".equals(format))set(changes,v,"storage-fmt","rawjpeg");
        String iso=String.valueOf(film[0]);
        if(supports(v,"iso-sensitivity",iso))set(changes,v,"iso-sensitivity",iso);
        else if(!iso.equals(v.get("iso-sensitivity")))body.note("ISO "+iso+" unavailable");
        if(supports(v,"whitebalance","color-temp") && v.get(KELVIN)!=null){
            set(changes,v,"whitebalance","color-temp");
            // Mode changes can reset the temperature. Send the value even if it matched before the switch.
            if(changes.containsKey("whitebalance"))changes.put(KELVIN,String.valueOf(film[1]));
            else set(changes,v,KELVIN,String.valueOf(film[1]));
        }
        v=commit(body,v,changes,"Capture",true);
        if("color-temp".equals(v.get("whitebalance"))){
            changes.clear();
            level(changes,v,AB,film[6]);
            level(changes,v,GM,-film[7]); // Sony counts magenta positive.
            for(Map.Entry<String,String> move:changes.entrySet()){
                String key=move.getKey(),before=v.get(key);
                if(!before.equals(lastShift.get(key)))originalShift.put(key,before);
                lastShift.put(key,move.getValue());
            }
            v=commit(body,v,changes,"White balance shift",false);
        }

        String style=film[2]==0x81?"standard":film[2]==0x83?"landscape":film[2]==0x86?"mono":null;
        if(style==null)return;
        if(!style.equals(v.get("color-mode"))){
            if(!supports(v,"color-mode",style)){body.note("Creative Style unavailable: "+style);return;}
            changes.clear();set(changes,v,"color-mode",style);
            v=commit(body,v,changes,"Creative Style",false);
            if(!style.equals(v.get("color-mode")))return;
        }
        // Switching styles may load that style's own adjustments, so use the readback.
        changes.clear();
        level(changes,v,"contrast",styleLevel(film[3]));
        if(!"mono".equals(style))level(changes,v,"saturation",styleLevel(film[4]));
        level(changes,v,"sharpness",styleLevel(film[5]-3));
        commit(body,v,changes,"Preview",false);
    }

    /** Sony can write WB fine tuning through to the system. Restore only axes still set by this session. */
    void restoreShift(Body body){
        if(originalShift.isEmpty())return;
        Values v=body.read();
        Map<String,String> changes=new LinkedHashMap<String,String>();
        for(String key:originalShift.keySet()){
            if(lastShift.get(key).equals(v.get(key)))set(changes,v,key,originalShift.get(key));
        }
        Values actual=commit(body,v,changes,"Restore white balance shift",false);
        for(String key:new String[]{AB,GM}){
            if(!changes.containsKey(key) || changes.get(key).equals(actual.get(key))){
                originalShift.remove(key);lastShift.remove(key);
            }
        }
    }
}

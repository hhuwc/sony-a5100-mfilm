package org.mfilm.sony;

public final class SonyFinderMeterTest {
    public interface Listener {void onEVRange(int thirds,Body source);}
    public static final class Range {public int wide=450,tele=450;}
    public static final class Lens {public Range MinFValue=new Range();public String LensName="Test 28/4.5";}
    public static final class Body {
        Listener listener;
        Lens lens=new Lens();
        public void setProgramLineRangeOverListener(Listener reflection){listener=reflection;}
        public Lens getLensInfo(){return lens;}
    }
    static void check(boolean ok){if(!ok)throw new AssertionError();}
    public static void main(String[] args) throws Exception{
        Body a=new Body(),b=new Body();
        int[] changes={0};
        SonyFinderMeter meter=new SonyFinderMeter(a,Listener.class,new Runnable(){public void run(){changes[0]++;}});
        check(meter.reading()==SonyFinderMeter.UNKNOWN);
        a.listener.onEVRange(0,a);a.listener.onEVRange(0,a);
        check(meter.reading()==0 && changes[0]==1);
        a.listener.onEVRange(-4,a);a.listener.onEVRange(5,b);
        check(meter.reading()==-4 && changes[0]==2);
        Listener old=a.listener;meter.close();old.onEVRange(9,a);
        check(meter.reading()==SonyFinderMeter.UNKNOWN && changes[0]==2 && a.listener==null);
        Object lens=SonyFinderMeter.lensInfo(a);
        check("Test 28/4.5".equals(SonyFinderMeter.lensName(lens)) && SonyFinderMeter.widest(lens,450)==450);
        a.lens.MinFValue.tele=560;
        check(SonyFinderMeter.widest(lens,800)==0 && SonyFinderMeter.widest(null,0)==0);
        check(SonyFinderMeter.lensInfo(new Object())==null && SonyFinderMeter.lensName(null)==null);
        System.out.println("PASS Sony listener identity, same-value suppression, signed thirds, release and stale callback, lens limits");
    }
}

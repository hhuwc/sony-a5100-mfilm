package org.mfilm.sony;

public final class MenuPressTest {
    private static void check(boolean ok) { if (!ok) throw new AssertionError(); }
    public static void main(String[] args) {
        MenuPress p=new MenuPress();
        check(p.start(10));
        check(!p.start(600)); // repeated DOWN cannot extend this press
        check(p.timer(2009)==MenuPress.Action.NONE);
        check(p.release(2009,false)==MenuPress.Action.BACK);
        check(p.timer(2010)==MenuPress.Action.NONE);
        check(p.start(3000));
        check(p.timer(5000)==MenuPress.Action.EXIT);
        check(p.timer(5005)==MenuPress.Action.NONE);
        check(p.release(5100,false)==MenuPress.Action.NONE);
        check(p.start(6000));
        check(p.release(8001,false)==MenuPress.Action.EXIT); // timer delayed by main loop
        check(p.release(8010,false)==MenuPress.Action.NONE);
        check(p.start(10000));
        p.cancel(); // lifecycle or window focus loss
        check(p.timer(14000)==MenuPress.Action.NONE);
        check(p.release(14001,false)==MenuPress.Action.NONE);
        check(p.start(16000));
        check(p.release(16020,true)==MenuPress.Action.NONE);
        check(p.start(18000));
        check(p.release(18100,false)==MenuPress.Action.BACK);
        System.out.println("PASS MENU short, deadline, repeat, late handler, cancellation and next press");
    }
}

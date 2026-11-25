package org.mfilm.sony;

public final class ShutterFocusTest implements ShutterFocus.Driver {
    final ShutterFocus shutter=new ShutterFocus(this);
    int id,requests,frames;
    public void requestFocus(int attempt){id=attempt;requests++;}
    public void expose(){frames++;}
    static void require(boolean ok){if(!ok)throw new AssertionError();}

    public static void main(String[] args){
        ShutterFocusTest t=new ShutterFocusTest();
        ShutterFocus f=t.shutter;
        f.halfDown(false);f.halfDown(false);
        require(t.requests==1);
        f.fullDown(false);
        require(t.frames==0);
        require(f.finish(t.id,true));
        require(t.frames==1);
        f.fullDown(false);
        require(!f.finish(t.id,true) && t.frames==1);
        f.reset();

        f.fullDown(false);
        int released=t.id;
        f.fullUp();
        require(f.finish(released,true) && t.frames==1);
        f.reset();
        f.fullDown(false);
        require(!f.finish(released,true));
        require(f.finish(t.id,false) && t.frames==1 && f.state==ShutterFocus.State.MISSED);
        require(!f.finish(t.id,true));
        f.reset();

        f.halfDown(false);
        require(f.finish(t.id,true) && t.frames==1);
        f.fullDown(false);
        require(t.frames==2);
        f.reset();
        f.fullDown(false);
        int paused=t.id;
        f.reset();
        require(!f.finish(paused,true) && t.frames==2);

        int before=t.requests;
        f.halfDown(true);f.fullDown(true);f.fullDown(true);
        require(t.requests==before && t.frames==3);
        f.reset();
        f.fullDown(true);
        require(t.requests==before && t.frames==4);
        System.out.println("Passed shutter sequencing, AF failure, cancellation, duplicate events and manual focus.");
    }
}

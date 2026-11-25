package org.mfilm.sony;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;

/** Read-only EV reports from one open CameraEx. Sony reports thirds of a stop. */
final class SonyFinderMeter implements InvocationHandler {
    static final int UNKNOWN=Integer.MIN_VALUE;
    private final Object camera;
    private final Runnable changed;
    private final Method setter;
    private volatile int thirds=UNKNOWN;
    private volatile boolean active=true;

    SonyFinderMeter(Object camera,Class<?> listener,Runnable changed) throws Exception {
        this.camera=camera;this.changed=changed;
        setter=camera.getClass().getMethod("setProgramLineRangeOverListener",listener);
        Object proxy=Proxy.newProxyInstance(listener.getClassLoader(),new Class<?>[]{listener},this);
        setter.invoke(camera,proxy);
    }
    int reading(){return active?thirds:UNKNOWN;}
    void close() throws Exception {
        active=false;
        setter.invoke(camera,new Object[]{null});
    }
    public Object invoke(Object proxy,Method method,Object[] args){
        String name=method.getName();
        if("onEVRange".equals(name) && active && args!=null && args.length==2 &&
                args[1]==camera && args[0] instanceof Integer){
            int value=(Integer)args[0];
            if(value!=thirds){thirds=value;changed.run();}
        }else if("hashCode".equals(name))return System.identityHashCode(proxy);
        else if("equals".equals(name))return proxy==args[0];
        else if("toString".equals(name))return "MFilm exposure meter";
        return null;
    }

    static Object lensInfo(Object camera){
        try{return camera.getClass().getMethod("getLensInfo").invoke(camera);}
        catch(Exception e){return null;}
    }
    static String lensName(Object lens){
        if(lens!=null)try{return (String)lens.getClass().getField("LensName").get(lens);}catch(Exception ignored){}
        return null;
    }
    /** A constant maximum aperture at both ends also applies at the current zoom position. */
    static int widest(Object lens,int measured){
        if(lens==null || measured<=0)return 0;
        try{
            Object limit=lens.getClass().getField("MinFValue").get(lens);
            int wide=limit.getClass().getField("wide").getInt(limit);
            int tele=limit.getClass().getField("tele").getInt(limit);
            if(wide==tele && wide>=95 && wide<=measured)return wide;
        }catch(Exception ignored){}
        return 0;
    }
}

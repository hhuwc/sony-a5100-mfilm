package org.mfilm.sony;

import android.app.Activity;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Rect;
import android.hardware.Camera;
import android.os.Bundle;
import android.os.Handler;
import android.os.SystemClock;
import android.util.Log;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.Locale;
import java.util.Map;
import java.util.Calendar;
import java.util.GregorianCalendar;
import java.util.TimeZone;
import java.lang.reflect.Method;

public final class FilmOS extends Activity implements SurfaceHolder.Callback {
    static { System.loadLibrary("filmos"); }
    private native boolean initialize(android.content.res.AssetManager assets);
    private native void runScreen(int page);
    private native void batteryLevel(int percent);
    private native boolean cardLogEnabled();
    private native void resetInput();
    private native void input(int key);
    private native void copyFrame(Bitmap image);
    private native void menuSurface(Surface surface);
    private native int remaining();
    private native boolean cleanFinder();
    private native boolean wantsMeter(boolean lit);
    private native String statusText();
    private native int[] filmSettings();
    private native int captureTicket();
    private native int attachFrame(int ticket,String path);
    private native boolean wind(boolean advance);
    private native int renderHud(boolean halfPressed,boolean manual,int ev,long now,long flashUntil);
    private native void alignClock(long localSeconds);
    private native int launchPage();
    private native int previousMenu();
    private native void updateExposure(int aperture,int widest,int numerator,int denominator,String lensName);

    private final File data=new File("/mnt/sdcard/MFILM");
    private static final int METER_REFRESH=1;
    private final Handler main=new Handler(){
        public void handleMessage(android.os.Message message){
            if(message.what==METER_REFRESH && meter!=null && resumed && !menu && !capturing)panel.invalidate();
        }
    };
    private SurfaceView preview;
    private SurfaceView filmSurface;
    private boolean directDisplay;
    private Panel panel;
    private TextView hud;
    private Object cameraEx;
    private Camera camera;
    private final StockSettings stock=new StockSettings();
    private final StockSettings.Body stockBody=new StockSettings.Body(){
        public StockSettings.Values read(){
            final Camera.Parameters values=camera.getParameters();
            return new StockSettings.Values(){public String get(String key){return values.get(key);}};
        }
        public void write(Map<String,String> changes,boolean capture)throws Exception{
            Camera.Parameters p=capture?camera.getParameters():
                (Camera.Parameters)cameraEx.getClass().getMethod("createEmptyParameters").invoke(cameraEx);
            for(Map.Entry<String,String> item:changes.entrySet())p.set(item.getKey(),item.getValue());
            camera.setParameters(p);
        }
        public void note(String message){log(message);}
    };
    private boolean resumed,ready,menu,capturing,surfaceReady,half;
    private boolean restorePausedMenu;
    private String captureFormat;
    private int focusSwitches;
    private boolean manualFocus;
    private String focusMode="AF",focusArea="";
    private String shutterSpeed="";
    private Runnable focusTimeout;
    private final ShutterFocus shutter=new ShutterFocus(new ShutterFocus.Driver(){
        public void requestFocus(int attempt){beginAutofocus(attempt);}
        public void expose(){shoot();}
    });
    private int rocker,zoomSpeed,previewMagnification;
    private int finderItem,magnifierX,magnifierY,magnifierBound;
    private boolean drivingLens;
    private long keyTime;
    private boolean tracing;
    private int held;
    private SonyFinderMeter meter;
    private boolean meterUnavailable;
    private long hudFlashUntil;
    private final BroadcastReceiver batteryChanges=new BroadcastReceiver(){
        public void onReceive(Context context,Intent message){
            int scale=message.getIntExtra("scale",0),level=message.getIntExtra("level",-1);
            batteryLevel(level>=0 && level<=scale && scale>0?100*level/scale:-1);
            if(!menu && ready)panel.invalidate();
        }
    };
    private final Runnable hudTick=new Runnable(){public void run(){
        if(resumed && ready && !menu)panel.invalidate();
    }};
    private final Runnable hideActions=new Runnable(){public void run(){
        if(!menu && resumed)hud.setVisibility(View.INVISIBLE);
    }};
    private final Runnable meterChanged=new Runnable(){public void run(){
        if(!main.hasMessages(METER_REFRESH))main.sendEmptyMessageDelayed(METER_REFRESH,80);
    }};
    private final Runnable endRoll=new Runnable(){public void run(){
        if(resumed && !menu && !capturing && remaining()==0)openPage(5);
    }};
    private String caption="Loading Film OS…   MENU · Exit";

    public void onCreate(Bundle b){
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        FrameLayout root=new FrameLayout(this);
        preview=new SurfaceView(this);
        preview.getHolder().setType(SurfaceHolder.SURFACE_TYPE_PUSH_BUFFERS);
        preview.getHolder().addCallback(this);root.addView(preview);
        filmSurface=new SurfaceView(this);
        filmSurface.setZOrderMediaOverlay(true);
        filmSurface.getHolder().setFormat(android.graphics.PixelFormat.RGBX_8888);
        filmSurface.getHolder().addCallback(new SurfaceHolder.Callback(){
            public void surfaceCreated(SurfaceHolder h){menuSurface(h.getSurface());}
            public void surfaceChanged(SurfaceHolder h,int format,int w,int height){menuSurface(h.getSurface());}
            public void surfaceDestroyed(SurfaceHolder h){menuSurface(null);if(menu)displayMode(false);}
        });
        filmSurface.setVisibility(View.GONE);root.addView(filmSurface);
        panel=new Panel();panel.setVisibility(View.GONE);root.addView(panel);
        hud=new TextView(this);hud.setTextColor(-1);hud.setBackgroundColor(0x99000000);
        root.addView(hud,new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM));setContentView(root);hud.setText(caption);
        new Thread(new Runnable(){public void run(){
            try{
                readCameraClock();
                if(!initialize(getAssets()))throw new IOException("Film OS fonts / stocks");
                tracing=new File(data,"TEST.ON").exists();
                if(tracing){
                    android.content.pm.PackageManager pm=getPackageManager();
                    android.content.pm.ActivityInfo entry=pm.getActivityInfo(getComponentName(),0);
                    Log.i("FilmOS","launcher label="+entry.loadLabel(pm)+" application="+
                        getApplicationInfo().loadLabel(pm)+" icon="+entry.getIconResource());
                }
                main.post(new Runnable(){public void run(){ready=true;if(resumed)enterFilmOS();}});
            }catch(Exception e){report("Card initialization",e);}
        }},"FilmOS-assets").start();
    }
    private int number(Object object,String field) throws Exception {
        return object.getClass().getField(field).getInt(object);
    }
    private void readCameraClock(){
        try{
            Class<?> time=Class.forName("com.sony.scalar.sysutil.TimeUtil");
            Object date=time.getMethod("getCurrentCalendar").invoke(null);
            // The ILCE-5100 supplies wall-clock fields, matching its ARW capture dates.
            Calendar local=new GregorianCalendar(TimeZone.getTimeZone("UTC"));
            local.clear();
            local.set(number(date,"year"),number(date,"month")-1,number(date,"day"),
                      number(date,"hour"),number(date,"minute"),number(date,"second"));
            alignClock(local.getTimeInMillis()/1000);
        }catch(Exception e){log("Camera clock unavailable: "+e);}
    }
    private void enterFilmOS(){
        int page=restorePausedMenu?previousMenu():launchPage();
        restorePausedMenu=false;
        if(page>=0){openPage(page);return;}
        panel.setVisibility(View.VISIBLE);
        finderItem=0;showFinderActions(true);
        startPreview();
    }
    private void report(String step,Throwable e){final String s=step+" · "+e.getMessage();log(s);main.post(new Runnable(){public void run(){if(!menu)finderText(s);Toast.makeText(FilmOS.this,s,Toast.LENGTH_LONG).show();}});}
    private synchronized void log(String s){
        Log.i("FilmOS",s);
        if(!cardLogEnabled())return;
        try{FileWriter f=new FileWriter(new File(data,"CAMERA.LOG"),true);try{f.write(SystemClock.uptimeMillis()+" "+s+"\n");}finally{f.close();}}catch(IOException ignored){}
    }
    private final class Panel extends View {
        final Bitmap bitmap=Bitmap.createBitmap(720,480,Bitmap.Config.ARGB_8888);
        final Rect dst=new Rect();
        Panel(){super(FilmOS.this);}
        protected void onDraw(Canvas canvas){
            long drawStart=tracing?SystemClock.uptimeMillis():0;
            if(!menu && ready && resumed){
                syncMeter();
                main.removeCallbacks(hudTick);
                long now=SystemClock.uptimeMillis();
                int delay=renderHud(half,manualFocus,meter==null?SonyFinderMeter.UNKNOWN:meter.reading(),now,hudFlashUntil);
                if(delay>0)main.postAtTime(hudTick,now+delay);
            }
            copyFrame(bitmap);
            int w=Math.min(getWidth(),getHeight()*3/2),h=w*2/3;
            dst.set((getWidth()-w)/2,(getHeight()-h)/2,(getWidth()+w)/2,(getHeight()+h)/2);
            if(menu)canvas.drawColor(0xff000000);
            canvas.drawBitmap(bitmap,null,dst,null);
            if(tracing && menu)Log.d("FilmFrame","draw "+drawStart+" "+SystemClock.uptimeMillis());
            if(tracing && keyTime!=0){Log.i("FilmOS","key to draw "+(SystemClock.uptimeMillis()-keyTime)+" ms");keyTime=0;}
        }
    }
    public void refresh(){panel.postInvalidate();}
    public void displayMode(final boolean direct){
        main.post(new Runnable(){public void run(){
            if(!menu)return;
            directDisplay=direct;
            panel.setVisibility(direct?View.INVISIBLE:View.VISIBLE);
            if(direct)keyTime=0;
        }});
    }
    private void openPage(final int page){
        if(!ready||!resumed||menu||capturing)return;
        stopMeter();main.removeCallbacks(hudTick);main.removeCallbacks(endRoll);main.removeCallbacks(hideActions);
        resetFocus();stopLens();clearMagnification();held=0;menu=true;resetInput();hud.setVisibility(View.GONE);panel.setVisibility(View.VISIBLE);
        directDisplay=false;filmSurface.setVisibility(View.VISIBLE);
        new Thread(new Runnable(){public void run(){
            try{runScreen(page);}finally{main.post(new Runnable(){public void run(){
                menu=false;directDisplay=false;filmSurface.setVisibility(View.GONE);
                if(resumed && restorePausedMenu){enterFilmOS();return;}
                panel.setVisibility(View.VISIBLE);panel.invalidate();hud.setVisibility(View.VISIBLE);
                finderItem=0;showFinderActions(true);
                if(resumed){startPreview();if(half && camera!=null && !capturing)shutter.halfDown(manualFocus);}
            }});}
        }},"FilmOS-ui").start();
    }
    public void cameraAction(final int act,int a,int b){
        main.post(new Runnable(){public void run(){
            if(act==3)finish();
            if(act==0||act==2){hudFlashUntil=0;applyStock();}
            if(act==1)restoreStockShift();
            if(act==5){WindowManager.LayoutParams p=getWindow().getAttributes();p.screenBrightness=a!=0?0.05f:-1f;getWindow().setAttributes(p);}
        }});
    }
    private void registerCameraKeys(){
        // Sony's foreground-app registration also controls which keys leave an app.
        Intent info=new Intent("com.android.server.DAConnectionManagerService.AppInfoReceive");
        info.putExtra("package_name",getComponentName().getPackageName());
        info.putExtra("class_name",getComponentName().getClassName());
        info.putExtra("pullingback_key",new String[]{"KEY_USB_CONNECT"});
        info.putExtra("resume_key",new String[0]);
        sendBroadcast(info);
    }
    protected void onResume(){
        super.onResume();
        resumed=true;
        registerReceiver(batteryChanges,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        registerCameraKeys();
        if(ready&&!menu)enterFilmOS();
    }
    protected void onPause(){
        resumed=false;
        unregisterReceiver(batteryChanges);
        main.removeCallbacks(hudTick);
        if(menu){restorePausedMenu=true;input(-1);}
        held=0;focusSwitches=0;half=false;
        releaseCamera();super.onPause();
    }
    public void surfaceCreated(SurfaceHolder h){surfaceReady=true;startPreview();}
    public void surfaceChanged(SurfaceHolder h,int format,int w,int height){startPreview();}
    public void surfaceDestroyed(SurfaceHolder h){surfaceReady=false;releaseCamera();}
    private void releaseCamera(){
        stopMeter();meterUnavailable=false;
        shutterSpeed="";updateExposure(0,0,0,0,null);
        resetFocus();half=false;focusSwitches=0;
        stopLens();clearMagnification();rocker=0;zoomSpeed=0;
        restoreStockShift();
        if(camera!=null)try{camera.stopPreview();}catch(Exception ignored){}
        if(cameraEx!=null)try{cameraEx.getClass().getMethod("release").invoke(cameraEx);}catch(Exception e){log("release "+e);}
        camera=null;cameraEx=null;captureFormat=null;
    }
    private void startPreview(){
        if(!resumed||!surfaceReady||menu||!ready||capturing)return;
        if(camera!=null){syncMeter();return;}
        try{
            Class<?> cls=Class.forName("com.sony.scalar.hardware.CameraEx");
            cameraEx=cls.getMethod("open",int.class,Class.forName(cls.getName()+"$OpenOptions")).invoke(null,0,null);
            camera=(Camera)cls.getMethod("getNormalCamera").invoke(cameraEx);
            camera.setPreviewDisplay(preview.getHolder());camera.startPreview();
            if(tracing)traceFocusAreas();
            configureZoom();
            if(ready)applyStock();syncMeter();log("Preview started");
        }catch(Exception e){releaseCamera();report("Live view",e);}
    }
    private void syncMeter(){
        if(meterUnavailable || cameraEx==null || capturing || menu || !resumed)return;
        if(!wantsMeter(half || SystemClock.uptimeMillis()<hudFlashUntil)){
            if(meter!=null)stopMeter();
            return;
        }
        if(meter!=null)return;
        try{
            Class<?> type=Class.forName("com.sony.scalar.hardware.CameraEx$ProgramLineRangeOverListener");
            meter=new SonyFinderMeter(cameraEx,type,meterChanged);
        }catch(Exception e){meterUnavailable=true;Log.i("FilmOS","EV meter unavailable: "+e);}
    }
    private void stopMeter(){
        SonyFinderMeter old=meter;meter=null;
        if(old!=null)try{old.close();}catch(Exception e){Log.w("FilmOS","detach EV meter",e);}
        main.removeMessages(METER_REFRESH);
    }
    private void configureZoom(){
        try{
            Class<?> listener=Class.forName("com.sony.scalar.hardware.CameraEx$PreviewMagnificationListener");
            Object scale=java.lang.reflect.Proxy.newProxyInstance(listener.getClassLoader(),new Class<?>[]{listener},
                new java.lang.reflect.InvocationHandler(){public Object invoke(Object proxy,Method method,Object[] args){
                    if("onChanged".equals(method.getName()) && args!=null && args.length>=2){
                        final int factor=(Integer)args[1];
                        main.post(new Runnable(){public void run(){magnifierBound=factor>100?1000-100000/factor:0;}});
                    }
                    return null;
                }});
            cameraEx.getClass().getMethod("setPreviewMagnificationListener",listener).invoke(cameraEx,scale);
        }catch(Exception e){Log.i("FilmOS","magnifier position unavailable: "+e);}
        try{
            Camera.Parameters p=camera.getParameters();
            Object m=cameraEx.getClass().getMethod("createParametersModifier",Camera.Parameters.class).invoke(cameraEx,p);
            java.util.List<?> modes=(java.util.List<?>)m.getClass().getMethod("getSupportedZoomDriveTypes").invoke(m);
            String optical=(String)m.getClass().getField("ZOOM_DRIVE_TYPE_OPTICAL").get(null);
            if(modes==null || !modes.contains(optical)){
                if(tracing)Log.i("FilmOS","lens has no optical zoom drive; preview magnifier available");
                return;
            }
            m.getClass().getMethod("setZoomDriveType",String.class).invoke(m,optical);
            camera.setParameters(p);
            zoomSpeed=(Integer)m.getClass().getMethod("getMaxZoomSpeed").invoke(m);
            if(tracing)Log.i("FilmOS","optical zoom max speed="+zoomSpeed);
        }catch(Exception e){Log.i("FilmOS","lens zoom unavailable: "+e);}
    }
    private void stopLens(){
        if(!drivingLens)return;
        drivingLens=false;
        try{cameraEx.getClass().getMethod("stopZoom").invoke(cameraEx);
            if(tracing)Log.i("FilmOS","zoom stopped focal_mm="+camera.getParameters().getFocalLength());
        }catch(Exception e){Log.w("FilmOS","stopZoom",e);}
    }
    private void clearMagnification(){
        if(previewMagnification==0)return;
        try{cameraEx.getClass().getMethod("stopPreviewMagnification").invoke(cameraEx);}
        catch(Exception e){Log.w("FilmOS","stopPreviewMagnification",e);}
        previewMagnification=magnifierX=magnifierY=magnifierBound=0;
    }
    private void magnifyPreview(int direction){
        int next=Math.max(0,Math.min(200,previewMagnification+direction*100));
        if(next==previewMagnification)return;
        if(next==0){clearMagnification();showFinderActions();return;}
        try{
            cameraEx.getClass().getMethod("setPreviewMagnification",int.class,android.util.Pair.class)
                .invoke(cameraEx,next,new android.util.Pair<Integer,Integer>(0,0));
            previewMagnification=next;magnifierX=magnifierY=0;
            finderText(statusText()+"    Focus magnifier · W to zoom out");
            if(tracing)Log.i("FilmOS","preview magnification="+next);
        }catch(Exception e){Log.w("FilmOS","setPreviewMagnification",e);}
    }
    private void finderText(String message){
        main.removeCallbacks(hideActions);hud.setVisibility(View.VISIBLE);hud.setText(message);
    }
    private void showFinderActions(){showFinderActions(false);}
    private void showFinderActions(boolean navigate){
        main.removeCallbacks(hideActions);
        boolean clean=cleanFinder();
        if(clean && !navigate){hud.setVisibility(View.INVISIBLE);return;}
        String[] names={wind(false)?"Wind":"Home","Film","Darkroom","Prints"};
        StringBuilder line=new StringBuilder();
        if(!clean)line.append(statusText()).append("    ");
        for(int i=0;i<names.length;i++)
            line.append(i==finderItem?"[":" ").append(names[i]).append(i==finderItem?"] ":"  ");
        finderText(line.toString());
        if(clean)main.postDelayed(hideActions,2500);
    }
    private void readFocusSettings(Camera.Parameters p){
        String mode=p.getFocusMode();
        manualFocus="manual".equals(mode) || "fixed".equals(mode) || "infinity".equals(mode) || "edof".equals(mode);
        String drive=p.get("af-mode"), area=p.get("focus-area-type");
        focusMode=manualFocus?"MF":(drive!=null?drive.toUpperCase(Locale.US):"AF");
        focusArea=area==null?"":area;
        Log.i("FilmOS","Focus mode="+mode+" drive="+drive+" area="+area);
    }
    private void traceFocusAreas(){
        try{
            Class<?> type=Class.forName("com.sony.scalar.hardware.CameraEx$AutoFocusDoneListener");
            Object listener=java.lang.reflect.Proxy.newProxyInstance(type.getClassLoader(),new Class<?>[]{type},
                new java.lang.reflect.InvocationHandler(){public Object invoke(Object proxy,Method method,Object[] args){
                    String name=method.getName();
                    if("onDone".equals(name) && args!=null && args.length>=2){
                        String areas=args[1] instanceof int[]?java.util.Arrays.toString((int[])args[1]):"unavailable";
                        Log.i("FilmOS","Sony AF status="+args[0]+" areas="+areas);
                    }
                    if("hashCode".equals(name))return System.identityHashCode(proxy);
                    if("equals".equals(name))return proxy==args[0];
                    if("toString".equals(name))return "MFilm AF listener";
                    return null;
                }});
            cameraEx.getClass().getMethod("setAutoFocusDoneListener",type).invoke(cameraEx,listener);
        }catch(Exception e){Log.i("FilmOS","AF areas unavailable: "+e);}
    }
    private void showFocus(){
        if(menu || capturing || !resumed)return;
        String result;
        switch(shutter.state){
            case SEARCHING: result="Focusing…";break;
            case LOCKED: result="Focus locked";break;
            case MISSED: result="No focus · Release and retry";break;
            case MANUAL: result="Manual focus";break;
            default: showFinderActions();return;
        }
        finderText(focusMode+(focusArea.length()==0?"":" · "+focusArea)+"    "+result+shutterSpeed);
        panel.invalidate();
    }
    private void clearFocusTimeout(){
        if(focusTimeout!=null){main.removeCallbacks(focusTimeout);focusTimeout=null;}
    }
    private void resetFocus(){
        boolean active=shutter.state!=ShutterFocus.State.IDLE && !manualFocus && !capturing;
        shutter.reset();clearFocusTimeout();
        if(active && camera!=null)try{camera.cancelAutoFocus();}catch(RuntimeException e){Log.w("FilmOS","cancel AF",e);}
    }
    private void beginAutofocus(final int request){
        clearMagnification();
        clearFocusTimeout();
        final Camera source=camera;
        final long start=SystemClock.uptimeMillis();
        focusTimeout=new Runnable(){public void run(){focusResult(request,source,false,start,"timeout");}};
        main.postDelayed(focusTimeout,6000);
        showFocus();
        try{
            source.autoFocus(new Camera.AutoFocusCallback(){
                public void onAutoFocus(boolean success,Camera from){focusResult(request,from,success,start,"camera");}
            });
        }catch(RuntimeException e){Log.w("FilmOS","start AF",e);focusResult(request,source,false,start,"error");}
    }
    private void focusResult(int request,Camera source,boolean success,long start,String reason){
        if(camera!=source || !shutter.finish(request,success))return;
        clearFocusTimeout();
        Log.i("FilmOS","AF result="+success+" reason="+reason+" elapsed_ms="+(SystemClock.uptimeMillis()-start)
                +" area="+focusArea+" shot="+(shutter.state==ShutterFocus.State.FIRED));
        if(!success)try{source.cancelAutoFocus();}catch(RuntimeException e){Log.w("FilmOS","cancel failed AF",e);}
        if(!capturing && success)try{readExposure(source.getParameters());}catch(RuntimeException e){Log.w("FilmOS","AF exposure",e);}
        showFocus();
    }
    private void moveFinder(int key){
        if(previewMagnification!=0){
            int step=Math.max(1,magnifierBound/4);
            int x=Math.max(-magnifierBound,Math.min(magnifierBound,magnifierX+(key==1?-step:key==2?step:0)));
            int y=Math.max(-magnifierBound,Math.min(magnifierBound,magnifierY+(key==3?-step:key==4?step:0)));
            if(x==magnifierX && y==magnifierY)return;
            try{
                cameraEx.getClass().getMethod("setPreviewMagnification",int.class,android.util.Pair.class)
                    .invoke(cameraEx,previewMagnification,new android.util.Pair<Integer,Integer>(x,y));
                magnifierX=x;magnifierY=y;
            }catch(Exception e){Log.w("FilmOS","pan magnifier",e);}
        }else if(key==1 || key==2){
            finderItem=Math.max(0,Math.min(3,finderItem+(key==2?1:-1)));
            showFinderActions(true);
        }
    }
    private boolean zoomEvent(int scan,KeyEvent event){
        int direction=scan==610?1:scan==611?-1:0;
        if(event.getAction()!=KeyEvent.ACTION_DOWN || rocker==direction)return true;
        stopLens();rocker=direction;
        if(tracing)Log.i("FilmOS","rocker="+direction+" menu="+menu);
        if(direction==0)return true;
        if(menu){input(direction>0?31:32);return true;}
        if(cameraEx==null || capturing)return true;
        if(zoomSpeed<=0){magnifyPreview(direction);return true;}
        try{
            int which=cameraEx.getClass().getField(direction>0?"ZOOM_DIRECTION_TELE":"ZOOM_DIRECTION_WIDE").getInt(null);
            cameraEx.getClass().getMethod("startZoom",int.class,int.class).invoke(cameraEx,which,zoomSpeed);
            drivingLens=true;
        }catch(Exception e){Log.w("FilmOS","startZoom",e);}
        return true;
    }
    private void restoreStockShift(){
        if(camera==null || capturing)return;
        try{stock.restoreShift(stockBody);}catch(RuntimeException e){log("Restore stock balance: "+e);}
    }
    private void applyStock(){
        if(camera==null || !ready || !resumed || capturing)return;
        try{
            int[] film=remaining()>0?filmSettings():null;
            if(film!=null)stock.apply(stockBody,film);
            else restoreStockShift();
            Camera.Parameters actual=camera.getParameters();
            captureFormat=actual.get("storage-fmt");
            readFocusSettings(actual);
            readExposure(actual);
            log("Capture storage="+actual.get("storage-fmt")+" ISO="+actual.get("iso-sensitivity")+
                " WB="+actual.getWhiteBalance()+" K="+actual.get(StockSettings.KELVIN)+
                " AB="+actual.get(StockSettings.AB)+" GM="+actual.get(StockSettings.GM)+
                " style="+actual.get("color-mode")+" contrast="+actual.get("contrast")+
                " saturation="+actual.get("saturation")+" sharpness="+actual.get("sharpness")+
                " EV index="+actual.get("exposure-compensation"));
        }catch(Exception e){report("Film settings",e);}
    }
    private void readExposure(Camera.Parameters params){
        int aperture=0,n=0,d=0;
        try{
            Object m=cameraEx.getClass().getMethod("createParametersModifier",Camera.Parameters.class)
                    .invoke(cameraEx,params);
            try{aperture=(Integer)m.getClass().getMethod("getAperture").invoke(m);}catch(Exception ignored){}
            android.util.Pair<?,?> speed=(android.util.Pair<?,?>)m.getClass().getMethod("getShutterSpeed").invoke(m);
            n=(Integer)speed.first;d=(Integer)speed.second;
        }catch(Exception ignored){}
        shutterSpeed=n>0 && d>0?"    "+(n==1 && d>1?"1/"+d:String.format(Locale.US,"%.2g",(double)n/d))+" s":"";
        Object lens=SonyFinderMeter.lensInfo(cameraEx);
        String name=SonyFinderMeter.lensName(lens);
        if(name==null || name.length()==0)name=aperture>0?"Sony E-mount":manualFocus?"Manual":"Lens info unavailable";
        updateExposure(aperture,SonyFinderMeter.widest(lens,aperture),n,d,name);
    }
    private void shoot(){
        if(menu||capturing||!ready||remaining()<=0||camera==null)return;
        if(captureFormat!=null && !"rawjpeg".equals(captureFormat) && !"raw".equals(captureFormat)){
            applyStock();
            if(!"rawjpeg".equals(captureFormat) && !"raw".equals(captureFormat)){
                report("Frame",new IOException("Camera is set to "+captureFormat+". Select RAW or RAW+JPEG"));return;
            }
        }
        final int ticket=captureTicket();
        if(ticket<0){report("Frame",new IOException("Could not recover the roll log"));return;}
        if(ticket==0){if(remaining()==0)openPage(5);return;}
        final File dcim=new File("/mnt/sdcard/DCIM");
        final CaptureFiles files;
        try{files=new CaptureFiles(dcim);}catch(IOException e){report("Card",e);return;}
        clearMagnification();
        stopMeter();capturing=true;finderText("Writing frame…");
        try{camera.takePicture(null,null,null);}catch(RuntimeException e){capturing=false;syncMeter();report("Shutter",e);return;}
        new Thread(new Runnable(){public void run(){
            try{
                String recorded=null;
                for(int i=0;i<100;i++){
                    Thread.sleep(200);
                    String path=files.stableFile(dcim);
                    if(path==null || !completeRaw(path))continue;
                    if(attachFrame(ticket,path)==0)throw new IOException("Could not save this frame to its roll");
                    recorded=path;break;
                }
                if(recorded==null)throw new IOException("No complete ARW. Check card and RAW image quality");
                log("Recorded "+recorded);
                main.post(new Runnable(){public void run(){
                    finderItem=0;hudFlashUntil=SystemClock.uptimeMillis()+2500;showFinderActions();panel.invalidate();
                    if(remaining()==0 && resumed)main.postDelayed(endRoll,1500);
                }});
            }catch(Exception e){report("Frame",e);}
            finally{main.post(new Runnable(){public void run(){capturing=false;
                if(resumed && !menu){
                    if(camera!=null)try{camera.startPreview();syncMeter();}catch(RuntimeException e){report("Preview restart",e);}
                    else startPreview();
                }
            }});}
        }},"FilmOS-card").start();
    }
    private native boolean completeRaw(String path);
    private static int key(KeyEvent e){
        switch(e.getScanCode()){
            case 105:return 1;case 106:return 2;case 103:case 608:return 3;case 108:return 4;
            case 232:return 7;case 514:case 229:return 8;case 207:return 10;
            case 595:case 513:return 9; // Sony guide/delete and its soft-key alias.
            case 516:case 517:return 20;case 518:return 21;
        }
        switch(e.getKeyCode()){
            case KeyEvent.KEYCODE_DPAD_LEFT:return 1;case KeyEvent.KEYCODE_DPAD_RIGHT:return 2;
            case KeyEvent.KEYCODE_DPAD_UP:return 3;case KeyEvent.KEYCODE_DPAD_DOWN:return 4;
            case KeyEvent.KEYCODE_DPAD_CENTER:case KeyEvent.KEYCODE_ENTER:return 7;
            case KeyEvent.KEYCODE_BACK:case KeyEvent.KEYCODE_MENU:return 8;
            case KeyEvent.KEYCODE_FOCUS:return 20;case KeyEvent.KEYCODE_CAMERA:return 21;default:return 0;
        }
    }
    public boolean dispatchKeyEvent(KeyEvent e){
        int scan=e.getScanCode();
        if(ready && (scan==610 || scan==611 || scan==645))return zoomEvent(scan,e);
        int k=key(e);
        if(!ready && k==8){if(e.getAction()==KeyEvent.ACTION_UP)finish();return true;}
        if(k==0||!ready)return super.dispatchKeyEvent(e);
        boolean down=e.getAction()==KeyEvent.ACTION_DOWN;
        if(tracing)Log.i("FilmOS","input key="+k+" scan="+e.getScanCode()+" down="+down);
        if(down&&e.getRepeatCount()!=0)return true;
        if(k==20){
            int bit=e.getScanCode()==516?1:e.getScanCode()==517?2:4;
            if(down)focusSwitches|=bit;else focusSwitches&=~bit;
            boolean pressed=focusSwitches!=0;
            if(half==pressed)return true;
            half=pressed;panel.invalidate();
            if(half&&menu){input(-1);return true;}
            if(half && !capturing && camera!=null)shutter.halfDown(manualFocus);
            else if(!half)resetFocus();
            showFocus();
        }else if(k==21){
            if(down){
                if(!menu && !capturing && camera!=null && remaining()>0){
                    shutter.fullDown(manualFocus);showFocus();
                }
            }else{
                shutter.fullUp();
                if(!half){resetFocus();if(!menu)showFocus();}
                if(capturing && cameraEx!=null)try{cameraEx.getClass().getMethod("cancelTakePicture").invoke(cameraEx);}catch(Exception ignored){}
            }
        }else if(down){held=k;}
        else if(k==held){
            held=0;
            if(menu){
                if(tracing && !directDisplay)keyTime=SystemClock.uptimeMillis();
                input(k);if(k<=4)input(k|256);
            }else if(!capturing){
                if(k>=1 && k<=4)moveFinder(k);
                else if(k==7 && previewMagnification==0){
                    if(finderItem==0 && wind(false)){
                        if(wind(true)){hudFlashUntil=SystemClock.uptimeMillis()+1500;showFinderActions();panel.invalidate();}
                        else report("Wind",new IOException("Could not save film advance"));
                    }
                    else openPage(finderItem==0?1:finderItem==1?0:finderItem==2?6:4);
                }
                else if(k==8)openPage(previousMenu());
                else if(k==10)openPage(4);
            }
        }
        return true;
    }
}

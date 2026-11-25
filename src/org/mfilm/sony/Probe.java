package org.mfilm.sony;
import android.app.Activity;
import android.os.Bundle;
import android.view.KeyEvent;
import android.widget.TextView;
import android.util.Log;

/** First on-body screen: the string comes across the same JNI library as Film OS. */
public final class Probe extends Activity {
    static { System.loadLibrary("filmos"); }
    private native String machine();
    private TextView label;
    public void onCreate(Bundle b) {
        super.onCreate(b); label=new TextView(this);label.setTextSize(24);setContentView(label);
        String s=machine()+"  API "+android.os.Build.VERSION.SDK_INT+
            "  cores "+Runtime.getRuntime().availableProcessors()+"  heap "+Runtime.getRuntime().maxMemory();
        try {s+="  FW "+Class.forName("com.sony.scalar.sysutil.ScalarProperties").getMethod("getFirmwareVersion").invoke(null);} catch(Exception ignored){}
        label.setText(s);Log.i("FilmOS",s);
    }
    public boolean onKeyDown(int code,KeyEvent e) {
        if(code==KeyEvent.KEYCODE_BACK)return super.onKeyDown(code,e);
        String s="key "+code+" scan "+e.getScanCode(); label.append("\n"+s);Log.i("FilmOS",s);return true;
    }
}

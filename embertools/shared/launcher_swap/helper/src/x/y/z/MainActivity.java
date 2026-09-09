package x.y.z;

import android.app.Activity;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.TextView;

/**
 * Tiny status screen. Also just a launch point so `am start` can pull the app
 * out of the "stopped" state after install so its services bind.
 */
public class MainActivity extends Activity {

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);

        boolean enabled = false;
        try {
            String flat = Settings.Secure.getString(getContentResolver(),
                    Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
            enabled = flat != null && flat.contains(getPackageName());
        } catch (Exception ignored) { }

        TextView tv = new TextView(this);
        tv.setPadding(48, 64, 48, 48);
        tv.setTextSize(15f);
        tv.setText("Home redirect helper\n\n"
                + "accessibility service active: " + enabled + "\n\n"
                + "Configured over ADB from a computer. If Home isn't going to your\n"
                + "launcher, re-run the setup tool with the reboot option.\n");
        setContentView(tv);
    }
}

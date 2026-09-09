package x.y.z;

import android.accessibilityservice.AccessibilityService;
import android.content.ComponentName;
import android.content.Intent;
import android.os.Handler;
import android.os.Message;
import android.os.SystemClock;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/**
 * Watches for a stock OEM launcher coming to the foreground and immediately
 * starts the user's chosen launcher instead.
 *
 * The redirect is only instant because this app also holds the voice-interaction
 * ("assistant") role -- that puts its uid in
 * ActivityManagerService.mAllowAppSwitchUids, exempting it from the ~5s
 * post-Home app-switch lock (AOSP APP_SWITCH_DELAY_TIME).  See AssistShimService.
 */
public class RedirectService extends AccessibilityService implements Handler.Callback {

    static final String TAG = "HomeRedirect";
    static final String TARGET_FILE = "/data/local/tmp/embertools_target";

    static final Set<String> BLOCKED = new HashSet<String>(Arrays.asList(
            "com.amazon.firelauncher",
            "com.amazon.tv.launcher",
            "com.android.launcher3"
    ));

    static String TARGET = "app.lawnchair";
    static String TARGET_ACTIVITY = "app.lawnchair.LawnchairLauncher";

    static final int MSG_RETRY = 1;
    static final long[] RETRIES = { 60, 180, 400, 900 };

    private Handler handler;
    private long lastLaunch = 0L;
    private int gen = 0;

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        handler = new Handler(getMainLooper(), this);
        loadTarget();
        Log.i(TAG, "connected target=" + TARGET);
        // Cold boot: the OEM launcher may already be in front before we bound
        // (no window event to react to), so nudge once now.
        handler.sendMessageDelayed(handler.obtainMessage(MSG_RETRY, gen, 0), 400);
    }

    private void loadTarget() {
        try {
            File f = new File(TARGET_FILE);
            if (!f.canRead()) return;
            BufferedReader r = new BufferedReader(new FileReader(f));
            String p = r.readLine();
            String a = r.readLine();
            r.close();
            if (p != null && p.trim().length() > 0) TARGET = p.trim();
            if (a != null && a.trim().length() > 0) TARGET_ACTIVITY = a.trim();
        } catch (Exception ignored) { }
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event == null || event.getPackageName() == null) return;
        if (event.getEventType() != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return;

        String pkg = event.getPackageName().toString();
        if (pkg.equals(getPackageName())) return;

        if (pkg.equals(TARGET)) {
            gen++;
            handler.removeMessages(MSG_RETRY);
            return;
        }
        if (!BLOCKED.contains(pkg)) return;

        long now = SystemClock.uptimeMillis();
        if (now - lastLaunch < 40) return;
        lastLaunch = now;

        final int myGen = ++gen;
        launchTarget();
        handler.removeMessages(MSG_RETRY);
        for (long d : RETRIES) {
            handler.sendMessageDelayed(handler.obtainMessage(MSG_RETRY, myGen, 0), d);
        }
    }

    @Override
    public boolean handleMessage(Message msg) {
        if (msg.what == MSG_RETRY && msg.arg1 == gen) launchTarget();
        return true;
    }

    private void launchTarget() {
        try {
            Intent i = new Intent(Intent.ACTION_MAIN);
            i.addCategory(Intent.CATEGORY_LAUNCHER);
            i.setComponent(new ComponentName(TARGET, TARGET_ACTIVITY));
            i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
            startActivity(i);
        } catch (Exception e) {
            Log.w(TAG, "launch failed", e);
        }
    }

    @Override
    public void onInterrupt() { }
}

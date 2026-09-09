package x.y.z;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

// Accessibility services are restarted automatically by the system on boot once
// enabled; this receiver is just a spare launch point.
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) { }
}

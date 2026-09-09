package x.y.z;

import android.service.voice.VoiceInteractionService;

/**
 * A do-nothing VoiceInteractionService.  Its only purpose: when this app is set
 * as Settings.Secure.VOICE_INTERACTION_SERVICE, VoiceInteractionManagerService
 * calls ActivityManagerService.setAllowAppSwitches() for this app's uid, which
 * exempts it from the post-Home app-switch lock and makes RedirectService's
 * launcher redirect instant instead of ~4.5s.
 *
 * supportsAssist is false in the metadata, so the assist gesture just no-ops
 * rather than opening a blank session.
 */
public class AssistShimService extends VoiceInteractionService {
}

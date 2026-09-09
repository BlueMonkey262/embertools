package x.y.z;

import android.content.Intent;
import android.speech.RecognitionService;
import android.speech.SpeechRecognizer;

// Required by the voice-interaction metadata (it must name a recognitionService).
// A no-op that immediately errors out. Never actually used.
public class AssistRecognitionService extends RecognitionService {
    @Override
    protected void onStartListening(Intent recognizerIntent, Callback listener) {
        try { listener.error(SpeechRecognizer.ERROR_CLIENT); } catch (Exception ignored) { }
    }

    @Override
    protected void onCancel(Callback listener) { }

    @Override
    protected void onStopListening(Callback listener) { }
}

package com.rex.rex

import android.content.Intent
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val channelName = "rex/voice_background"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            channelName
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                "start" -> {
                    startVoiceService()
                    result.success(null)
                }
                "stop" -> {
                    stopService(Intent(this, RexVoiceForegroundService::class.java))
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
    }

    private fun startVoiceService() {
        val intent = Intent(this, RexVoiceForegroundService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }
}

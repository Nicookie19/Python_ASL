import QtQuick 2.15
import QtMultimedia 2.15
import QtQuick.Controls 2.15

Item {
    id: camera
    property string deviceId: ""
    property bool mirror: true
    property int targetFps: 30
    property int resolutionWidth: 640
    property int resolutionHeight: 480
    property bool running: false

    signal frameReady(object frame)  // QVideoFrame
    signal errorOccurred(string message)
    signal started(string deviceId)
    signal stopped(string deviceId)
    signal staticFeedDetected(string message)

    Camera {
        id: camera
        deviceId: cameraDeviceId
    }

    MediaCaptureSession {
        id: captureSession
        camera: camera
        videoSink: videoSink
    }

    VideoSink {
        id: videoSink
        onVideoFrameChanged: {
            if (camera.running) {
                camera.frameReady(videoFrame)
            }
        }
    }

    property string cameraDeviceId: ""

    property bool running: false

    function start() {
        if (!running) {
            // Find the Qt camera device by ID
            var qtDevice = null
            var devices = QtMultimedia.availableCameras
            for (var i = 0; i < devices.length; i++) {
                if (devices[i].deviceId === camera.deviceId) {
                    cameraDeviceId = devices[i].deviceId
                    break
                }
            }
            if (!cameraDeviceId) {
                console.error("Camera device not found")
                return
            }
            running = true
        }
    }

    function stop() {
        running = false
    }

    function setDeviceId(deviceId) {
        if (camera.deviceId !== deviceId) {
            camera.stop()
            camera.deviceId = deviceId
            if (running) {
                camera.start()
            }
        }
    }

    function setMirror(mirror) {
        // Mirror is handled in QML display
    }

    function setResolution(width, height) {
        // Resolution is handled by the camera
    }

    function setTargetFps(fps) {
        // FPS is handled by the camera
    }

    Component.onCompleted: {
        // Camera will be started when running is set to true
    }

    onRunningChanged: {
        if (running) {
            console.log("Camera started:", cameraDeviceId)
        } else {
            console.log("Camera stopped")
        }
    }
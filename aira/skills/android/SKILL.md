# Android CLI Development

Full Android development from the command line.

## Project Scaffolding
```bash
# Create a new Android project
mkdir -p app/src/main/java/com/example/{name} app/src/main/res/layout
# Build with Gradle
gradle wrapper && ./gradlew assembleDebug
# Or use Android SDK directly
"$ANDROID_HOME/tools/bin/avdmanager" create avd -n pixel6 -k "system-images;android-33;google_apis;x86_64"
```

## ADB Commands
```bash
adb devices                    # List connected devices
adb install app-debug.apk      # Install APK
adb logcat -d                  # Dump device log
adb shell dumpsys              # System diagnostics
adb shell am start -n com.example.{name}/.MainActivity
```

## SDK Management
```bash
sdkmanager --list                    # Available packages
sdkmanager "platforms;android-33"    # Install platform
sdkmanager --update                  # Update SDK
echo $ANDROID_HOME                   # Verify SDK path
```

## Gradle Build
```bash
./gradlew assembleDebug       # Debug build
./gradlew test                # Run unit tests
./gradlew lint                # Static analysis
./gradlew bundleDebug         # App bundle
```

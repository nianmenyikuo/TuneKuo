plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.personal.tunebox"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.personal.tunebox"
        minSdk = 24          // Android 7.0
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
        // 32 位优先（armeabi-v7a），同时保留 arm64 以便新机用户自选
        ndk {
            abiFilters += listOf("armeabi-v7a", "arm64-v8a")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.media:media:1.7.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    // libVLC：全格式解码（FLAC/APE/DSD/AC-3/E-AC-3/TrueHD/DTS/ALAC/WavPack/TAK/TTA…）
    implementation("org.videolan.android:libvlc-all:3.6.5")
}

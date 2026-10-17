plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.personal.tunebox"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.personal.tunebox"
        minSdk = 24
        targetSdk = 34
        versionCode = 5
        versionName = "1.0.5"
        val abis = mutableListOf("armeabi-v7a", "arm64-v8a")
        if (project.hasProperty("emu")) abis.add("x86_64")
        ndk {
            abiFilters += abis
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
    implementation("org.videolan.android:libvlc-all:3.6.5")
}

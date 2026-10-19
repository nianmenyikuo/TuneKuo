plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val versionNameFromFile = rootProject.file("VERSION").readText().trim()
val versionNumbers = versionNameFromFile.split(".")
val versionCodeFromFile = versionNumbers[0].toInt() * 10000 +
        versionNumbers[1].toInt() * 100 +
        versionNumbers[2].toInt()

val keystorePropsFile = rootProject.file("keystore.properties")
val keystoreProps: Map<String, String> = if (keystorePropsFile.exists()) {
    keystorePropsFile.readLines()
        .map { it.trim() }
        .filter { it.isNotEmpty() && !it.startsWith("#") && it.contains("=") }
        .associate { it.substringBefore("=").trim() to it.substringAfter("=").trim() }
} else {
    emptyMap()
}
val hasReleaseKey = keystoreProps["storeFile"] != null

android {
    namespace = "com.personal.tunebox"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.personal.tunebox"
        minSdk = 24
        targetSdk = 34
        versionCode = versionCodeFromFile
        versionName = versionNameFromFile
        val abis = mutableListOf("armeabi-v7a", "arm64-v8a")
        if (project.hasProperty("emu")) abis.add("x86_64")
        ndk {
            abiFilters += abis
        }
    }

    if (hasReleaseKey) {
        signingConfigs {
            create("release") {
                storeFile = rootProject.file(keystoreProps.getValue("storeFile"))
                storePassword = keystoreProps.getValue("storePassword")
                keyAlias = keystoreProps.getValue("keyAlias")
                keyPassword = keystoreProps.getValue("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (hasReleaseKey) {
                signingConfig = signingConfigs.getByName("release")
            }
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
    implementation("com.google.android.material:material:1.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    implementation("org.videolan.android:libvlc-all:3.6.5")
}

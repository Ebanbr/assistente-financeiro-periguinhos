import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Assinatura fixa (sempre a mesma chave, senão o celular recusa a atualização).
// keystore.properties e a chave ficam só no PC, fora do Git.
val assinatura = Properties().apply {
    val arquivo = rootProject.file("keystore.properties")
    if (arquivo.exists()) arquivo.inputStream().use { load(it) }
}

android {
    namespace = "br.periguinhos.semana"
    compileSdk = 36

    defaultConfig {
        applicationId = "br.periguinhos.semana"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"
        // endereço da API no Google Cloud Run (dá para trocar na tela de login)
        buildConfigField("String", "API_URL", "\"${project.findProperty("apiUrl") ?: ""}\"")
    }

    signingConfigs {
        if (assinatura.containsKey("storeFile")) {
            create("periguinhos") {
                storeFile = file(assinatura.getProperty("storeFile"))
                storePassword = assinatura.getProperty("storePassword")
                keyAlias = assinatura.getProperty("keyAlias")
                keyPassword = assinatura.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("periguinhos")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    val bom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(bom)
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-play-services:1.9.0")
    // leitor de QR do Google Play Services (o mesmo da câmera do Android)
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")
}

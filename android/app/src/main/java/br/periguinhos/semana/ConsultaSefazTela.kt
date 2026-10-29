package br.periguinhos.semana

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

private const val CONSULTA_CHAVE = "https://nfce.sefaz.pe.gov.br:444/nfce-web/entradaConsNfce?tp=C"

/**
 * Consulta completa da nota pela chave, no site da SEFAZ-PE, dentro do app. A chave já vem preenchida;
 * a pessoa marca o "Não sou um robô" e toca em Consultar. Quando a nota aparece, o app lê a página e
 * segue para a tela do cupom com os itens (nota de contingência que o link do QR não devolve).
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun ConsultaSefazTela(api: Api, chave: String, aoLido: (JSONObject) -> Unit, aoSair: (Boolean) -> Unit) {
    val contexto = LocalContext.current
    val escopo = rememberCoroutineScope()
    var lendo by remember { mutableStateOf(false) }
    var carregandoPagina by remember { mutableStateOf(true) }

    fun lerPagina(html: String) {
        if (lendo) return
        lendo = true
        escopo.launch {
            try {
                aoLido(api.lerCupomPagina(chave, html).put("_html", html))
            } catch (e: ApiErro) {
                Toast.makeText(contexto, e.message, Toast.LENGTH_LONG).show()
                lendo = false
            }
        }
    }

    Column(Modifier.fillMaxSize()) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
            IconButton(onClick = { aoSair(false) }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Voltar") }
            Column(Modifier.weight(1f)) {
                Text("🔎 Consulta na SEFAZ", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
                Text(if (lendo) "Lendo os itens da nota…" else "Marque \"Não sou um robô\" e toque em Consultar.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
            }
        }
        if (carregandoPagina || lendo) LinearProgressIndicator(Modifier.fillMaxWidth())
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                WebView(ctx).apply {
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    webViewClient = object : WebViewClient() {
                        override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
                            carregandoPagina = true
                        }

                        override fun onPageFinished(view: WebView, url: String?) {
                            carregandoPagina = false
                            val endereco = url.orEmpty()
                            if ("entradaConsNfce" in endereco) {
                                // só preenche o campo da chave; o "Não sou um robô" e o Consultar são da pessoa
                                view.evaluateJavascript(
                                    "var c=document.getElementById('chave'); if(c){c.value='$chave';}", null)
                            } else if ("/consNfce" in endereco) {
                                view.evaluateJavascript(
                                    "document.getElementById('produtos') ? document.documentElement.outerHTML : ''",
                                ) { r -> JSONArray("[$r]").optString(0).takeIf { it.isNotBlank() }?.let(::lerPagina) }
                            }
                        }
                    }
                    loadUrl(CONSULTA_CHAVE)
                }
            },
        )
    }
}

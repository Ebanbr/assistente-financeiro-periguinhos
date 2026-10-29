package br.periguinhos.semana

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val api = Api(getSharedPreferences("periguinhos", MODE_PRIVATE))
        setContent {
            Tema {
                Surface(Modifier.fillMaxSize().systemBarsPadding().imePadding(), color = MaterialTheme.colorScheme.background) {
                    App(api)
                }
            }
        }
    }
}

/** Telas além da semana. */
sealed interface Tela {
    data object Semana : Tela
    data class Gasto(val linha: Linha?) : Tela
    data class Cupom(val leitura: JSONObject, val link: String) : Tela
    data class Consulta(val chave: String) : Tela
}

@Composable
fun App(api: Api) {
    if (api.sessaoExpirada.value) {
        Login(api)
        return
    }
    var tela by remember { mutableStateOf<Tela>(Tela.Semana) }
    var opcoes by remember { mutableStateOf<Opcoes?>(null) }
    var recarga by remember { mutableStateOf(0) }
    val voltar: (Boolean) -> Unit = { mudou -> if (mudou) recarga++; tela = Tela.Semana }
    BackHandler(enabled = tela != Tela.Semana) { voltar(false) }

    when (val t = tela) {
        Tela.Semana -> SemanaTela(
            api, recarga, aoCarregarOpcoes = { opcoes = it },
            aoNovoGasto = { tela = Tela.Gasto(null) },
            aoEditar = { tela = Tela.Gasto(it) },
            aoCupom = { leitura, link -> tela = Tela.Cupom(leitura, link) },
            aoConsultarSefaz = { tela = Tela.Consulta(it) },
        )
        is Tela.Gasto -> opcoes?.let { GastoTela(api, it, t.linha, voltar) } ?: Carregando()
        is Tela.Cupom -> opcoes?.let {
            CupomTela(api, it, t.leitura, t.link, voltar, aoConsultarSefaz = { chave -> tela = Tela.Consulta(chave) })
        } ?: Carregando()
        is Tela.Consulta -> ConsultaSefazTela(api, t.chave, aoLido = { tela = Tela.Cupom(it, "") }, aoSair = voltar)
    }
}

@Composable
fun Carregando() = Column(Modifier.fillMaxSize().padding(48.dp)) { CircularProgressIndicator() }

@Composable
fun Login(api: Api) {
    var usuario by remember { mutableStateOf(api.usuario) }
    var senha by remember { mutableStateOf("") }
    var servidor by remember { mutableStateOf(api.base) }
    var mostrarServidor by remember { mutableStateOf(api.base.isBlank()) }
    var erro by remember { mutableStateOf<String?>(null) }
    var entrando by remember { mutableStateOf(false) }
    val escopo = rememberCoroutineScope()

    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("🐧 Periguinhos", fontSize = 30.sp, modifier = Modifier.padding(top = 48.dp))
        Text("Gastos da semana", color = MaterialTheme.colorScheme.onSurfaceVariant)
        OutlinedTextField(usuario, { usuario = it }, label = { Text("Usuário") }, singleLine = true,
            modifier = Modifier.fillMaxWidth())
        OutlinedTextField(senha, { senha = it }, label = { Text("Senha") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth())
        if (mostrarServidor) {
            OutlinedTextField(servidor, { servidor = it }, label = { Text("Endereço do servidor") }, singleLine = true,
                placeholder = { Text("https://…run.app") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                modifier = Modifier.fillMaxWidth())
        } else {
            TextButton(onClick = { mostrarServidor = true }) { Text("Trocar servidor") }
        }
        erro?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(
            enabled = !entrando && usuario.isNotBlank() && senha.isNotBlank(),
            onClick = {
                entrando = true; erro = null
                escopo.launch {
                    try {
                        api.base = servidor
                        api.entrar(usuario.trim(), senha)
                    } catch (e: ApiErro) {
                        erro = e.message
                    } finally {
                        entrando = false
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(),
        ) { Text(if (entrando) "Entrando…" else "Entrar") }
    }
}

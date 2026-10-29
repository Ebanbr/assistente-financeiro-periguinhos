package br.periguinhos.semana

import android.content.SharedPreferences
import androidx.compose.runtime.mutableStateOf
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/** Erro que vai direto para a tela (a API já manda a mensagem em português). */
class ApiErro(mensagem: String, val codigo: Int = 0) : Exception(mensagem)

/** Conversa com a API do Google Cloud Run. Guarda endereço, token e usuário no celular. */
class Api(private val prefs: SharedPreferences) {

    /** Vira true quando a API recusa o token: o app volta para o login. */
    val sessaoExpirada = mutableStateOf(prefs.getString("token", null) == null)

    var base: String
        get() = prefs.getString("base", null) ?: BuildConfig.API_URL
        set(v) = prefs.edit().putString("base", v.trim().trimEnd('/')).apply()

    var usuario: String
        get() = prefs.getString("usuario", "") ?: ""
        private set(v) = prefs.edit().putString("usuario", v).apply()

    private val token: String? get() = prefs.getString("token", null)

    fun sair() {
        prefs.edit().remove("token").apply()
        sessaoExpirada.value = true
    }

    private suspend fun chamar(metodo: String, caminho: String, corpo: JSONObject? = null): String =
        withContext(Dispatchers.IO) {
            if (base.isBlank()) throw ApiErro("Informe o endereço do servidor.")
            val con = try {
                URL(base + caminho).openConnection() as HttpURLConnection
            } catch (e: Exception) {
                throw ApiErro("Endereço do servidor inválido.")
            }
            try {
                con.requestMethod = metodo
                con.connectTimeout = 20_000
                con.readTimeout = 90_000   // a 1ª chamada acorda o servidor e lê a planilha
                con.setRequestProperty("Accept", "application/json")
                token?.let { con.setRequestProperty("Authorization", "Bearer $it") }
                if (corpo != null) {
                    con.doOutput = true
                    con.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    con.outputStream.use { it.write(corpo.toString().toByteArray(Charsets.UTF_8)) }
                }
                val codigo = con.responseCode
                val texto = (if (codigo < 400) con.inputStream else con.errorStream)
                    ?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
                if (codigo == 401 && caminho != "/login") {
                    prefs.edit().remove("token").apply()
                    sessaoExpirada.value = true
                }
                if (codigo >= 400) {
                    val detalhe = runCatching { JSONObject(texto).opt("detail") }.getOrNull()
                    val msg = when (detalhe) {
                        is String -> detalhe
                        null -> "Erro $codigo no servidor."
                        else -> "Dados inválidos ($codigo)."
                    }
                    throw ApiErro(msg, codigo)
                }
                texto
            } catch (e: ApiErro) {
                throw e
            } catch (e: Exception) {
                throw ApiErro("Sem conexão com o servidor. Confira a internet e tente de novo.")
            } finally {
                con.disconnect()
            }
        }

    suspend fun entrar(usuario: String, senha: String) {
        val r = JSONObject(chamar("POST", "/login", JSONObject().put("usuario", usuario).put("senha", senha)))
        prefs.edit().putString("token", r.getString("token")).apply()
        this.usuario = r.getString("usuario")
        sessaoExpirada.value = false
    }

    suspend fun opcoes(): Opcoes = Opcoes.de(JSONObject(chamar("GET", "/opcoes")))

    suspend fun semana(dia: String?): Semana =
        Semana.de(JSONObject(chamar("GET", "/semana" + (dia?.let { "?dia=$it" } ?: ""))))

    suspend fun sugestao(descricao: String): String? {
        val r = JSONObject(chamar("GET", "/sugestao?descricao=" + URLEncoder.encode(descricao, "UTF-8")))
        return r.optString("categoria").takeIf { it.isNotBlank() && it != "null" }
    }

    suspend fun salvarGasto(id: String?, gasto: JSONObject) {
        chamar("POST", if (id == null) "/gastos" else "/gastos/$id", gasto)
    }

    suspend fun excluirGasto(id: String) {
        chamar("DELETE", "/gastos/$id")
    }

    suspend fun lerCupom(link: String): JSONObject =
        JSONObject(chamar("POST", "/cupom/ler", JSONObject().put("link", link)))

    suspend fun lerCupomPagina(chave: String, html: String): JSONObject =
        JSONObject(chamar("POST", "/cupom/pagina", JSONObject().put("chave", chave).put("html", html)))

    suspend fun lancarCupom(pedido: JSONObject): JSONObject = JSONObject(chamar("POST", "/cupom/lancar", pedido))

    suspend fun lancarSoTotal(pedido: JSONObject): JSONObject = JSONObject(chamar("POST", "/cupom/so-total", pedido))

    suspend fun cuponsEsperando(): List<CupomEsperando> {
        val a = JSONArray(chamar("GET", "/cupom/esperando"))
        return (0 until a.length()).map { CupomEsperando.de(a.getJSONObject(it)) }
    }

    suspend fun ficarSoComTotal(chave: String) {
        chamar("POST", "/cupom/$chave/ficar-so-com-total")
    }
}

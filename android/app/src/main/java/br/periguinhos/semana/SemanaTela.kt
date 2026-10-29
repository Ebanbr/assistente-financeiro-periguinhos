package br.periguinhos.semana

import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import org.json.JSONObject
import java.time.LocalDate

/** Abre o leitor de QR do Google; devolve o texto lido ou null se a pessoa cancelou. */
suspend fun lerQr(contexto: Context): String? {
    val opcoes = GmsBarcodeScannerOptions.Builder()
        .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
        .enableAutoZoom()
        .build()
    return GmsBarcodeScanning.getClient(contexto, opcoes).startScan().await()?.rawValue
}

@Composable
fun SemanaTela(
    api: Api, recarga: Int,
    aoCarregarOpcoes: (Opcoes) -> Unit,
    aoNovoGasto: () -> Unit,
    aoEditar: (Linha) -> Unit,
    aoCupom: (JSONObject, String) -> Unit,
    aoConsultarSefaz: (String) -> Unit,
) {
    val contexto = LocalContext.current
    val escopo = rememberCoroutineScope()
    var referencia by rememberSaveable { mutableStateOf(LocalDate.now().toString()) }
    var semana by remember { mutableStateOf<Semana?>(null) }
    var esperando by remember { mutableStateOf<List<CupomEsperando>>(emptyList()) }
    var erro by remember { mutableStateOf<String?>(null) }
    var carregando by remember { mutableStateOf(false) }
    var lendo by remember { mutableStateOf(false) }
    var atualizar by remember { mutableStateOf(0) }
    var colarLink by remember { mutableStateOf(false) }
    var semItens by remember { mutableStateOf<CupomEsperando?>(null) }

    LaunchedEffect(referencia, recarga, atualizar) {
        carregando = true; erro = null
        try {
            semana = api.semana(referencia)
            esperando = api.cuponsEsperando()
            aoCarregarOpcoes(api.opcoes())
        } catch (e: ApiErro) {
            erro = e.message
        } finally {
            carregando = false
        }
    }

    fun abrirCupom(link: String, esperado: CupomEsperando? = null) {
        lendo = true
        escopo.launch {
            try {
                val leitura = api.lerCupom(link)
                when {
                    esperado != null && leitura.optString("status") == "pendente" ->
                        Toast.makeText(contexto, leitura.optString("mensagem").ifBlank { "A SEFAZ ainda não recebeu essa nota." },
                            Toast.LENGTH_LONG).show()
                    esperado != null && leitura.optString("status") == "sem_itens" -> semItens = esperado
                    else -> aoCupom(leitura, link)
                }
            } catch (e: ApiErro) {
                Toast.makeText(contexto, e.message, Toast.LENGTH_LONG).show()
            } finally {
                lendo = false
            }
        }
    }

    val hoje = LocalDate.now()
    val ref = LocalDate.parse(referencia)
    LazyColumn(
        Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("🐧 Semana", fontSize = 22.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                IconButton(onClick = { atualizar++ }) { Icon(Icons.Default.Refresh, "Atualizar") }
                IconButton(onClick = { api.sair() }) { Icon(Icons.AutoMirrored.Filled.Logout, "Sair") }
            }
        }
        item {
            val proximaSegunda = ref.plusDays(8L - ref.dayOfWeek.value)
            CartaoSemana(semana, carregando, podeAvancar = !proximaSegunda.isAfter(hoje),
                aoVoltar = { referencia = ref.minusDays(7).toString() },
                aoAvancar = { referencia = minOf(ref.plusDays(7), hoje).toString() })
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(
                    enabled = !lendo,
                    onClick = {
                        escopo.launch {
                            try {
                                lerQr(contexto)?.let { abrirCupom(it) }
                            } catch (e: Exception) {
                                Toast.makeText(contexto, "Não consegui abrir o leitor de QR. Use colar o link.",
                                    Toast.LENGTH_LONG).show()
                            }
                        }
                    },
                    modifier = Modifier.weight(1f).height(52.dp),
                ) {
                    Icon(Icons.Default.QrCodeScanner, null); Spacer(Modifier.width(8.dp))
                    Text(if (lendo) "Lendo cupom…" else "Ler cupom")
                }
                OutlinedButton(onClick = aoNovoGasto, modifier = Modifier.weight(1f).height(52.dp)) {
                    Icon(Icons.Default.Add, null); Spacer(Modifier.width(8.dp)); Text("Gasto")
                }
            }
            TextButton(onClick = { colarLink = true }) {
                Icon(Icons.Default.Link, null); Spacer(Modifier.width(6.dp)); Text("Colar o link do QR Code")
            }
        }
        erro?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        if (esperando.isNotEmpty()) {
            item { Titulo("⏳ Esperando a SEFAZ") }
            items(esperando, key = { it.chave }) { c ->
                Bloco {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(c.estabelecimento.ifBlank { "Cupom" })
                            Text("${dataBr(c.data)} · ${reais(c.valor)}", color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontSize = 13.sp)
                        }
                        TextButton(enabled = !lendo, onClick = { abrirCupom(c.link, c) }) { Text("Já chegou?") }
                    }
                }
            }
        }
        val s = semana
        if (s != null && s.dias.isEmpty() && !carregando) {
            item {
                Text(if (s.encerrada) "Essa semana já ficou na fatura encerrada." else "Nenhum gasto nesta semana ainda.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(vertical = 16.dp))
            }
        }
        s?.dias?.forEach { dia ->
            item(key = "dia-" + dia.data) {
                Row(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                    Text("${dia.nome}, ${diaMes(dia.data)}", fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                    Text(reais(dia.total), fontWeight = FontWeight.SemiBold)
                }
            }
            items(dia.compras, key = { c -> "c-" + dia.data + (c.chave ?: c.linhas.firstOrNull()?.id) }) { compra ->
                CompraCartao(compra, aoEditar)
            }
        }
        if (s != null && s.resumo.isNotEmpty()) {
            item { Titulo("Por categoria") }
            item { Resumo(s.resumo) }
        }
        item { Spacer(Modifier.height(32.dp)) }
    }

    if (colarLink) {
        var link by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { colarLink = false },
            title = { Text("Link do QR Code") },
            text = {
                OutlinedTextField(link, { link = it }, placeholder = { Text("http://nfce.sefaz.pe.gov.br/…") },
                    modifier = Modifier.fillMaxWidth())
            },
            confirmButton = {
                TextButton(enabled = link.isNotBlank(), onClick = { colarLink = false; abrirCupom(link.trim()) }) {
                    Text("Ler cupom")
                }
            },
            dismissButton = { TextButton(onClick = { colarLink = false }) { Text("Cancelar") } },
        )
    }

    semItens?.let { c ->
        AlertDialog(
            onDismissRequest = { semItens = null },
            title = { Text("Sem os itens") },
            text = {
                Text("A nota já chegou na SEFAZ, mas ela não devolve os itens pelo QR Code. O gasto continua " +
                    "lançado com o total (${reais(c.valor)}). Dá para pegar os itens consultando a nota pela chave " +
                    "no site da SEFAZ (você marca o \"Não sou um robô\").")
            },
            confirmButton = {
                TextButton(onClick = { semItens = null; aoConsultarSefaz(c.chave) }) { Text("Consultar na SEFAZ") }
            },
            dismissButton = {
                TextButton(onClick = {
                    semItens = null
                    escopo.launch {
                        try {
                            api.ficarSoComTotal(c.chave); atualizar++
                        } catch (e: ApiErro) {
                            Toast.makeText(contexto, e.message, Toast.LENGTH_LONG).show()
                        }
                    }
                }) { Text("Ficar só com o total") }
            },
        )
    }
}

@Composable
private fun Titulo(texto: String) =
    Text(texto, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 12.dp))

@Composable
fun Bloco(conteudo: @Composable () -> Unit) = Card(
    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer),
    shape = RoundedCornerShape(14.dp),
    modifier = Modifier.fillMaxWidth(),
) { Box(Modifier.padding(14.dp)) { conteudo() } }

@Composable
private fun CartaoSemana(s: Semana?, carregando: Boolean, podeAvancar: Boolean, aoVoltar: () -> Unit, aoAvancar: () -> Unit) {
    Bloco {
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = aoVoltar) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Semana anterior") }
                Text(
                    s?.let { "${diaMes(it.inicio)} a ${diaMes(it.fim)}" + if (it.recortada) " · recortada" else "" } ?: "…",
                    modifier = Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                IconButton(onClick = aoAvancar, enabled = podeAvancar) {
                    Icon(Icons.AutoMirrored.Filled.ArrowForward, "Próxima semana")
                }
            }
            if (carregando && s == null) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                return@Column
            }
            if (s == null) return@Column
            Text(reais(s.total), fontSize = 34.sp, fontWeight = FontWeight.Bold)
            if (s.limite > 0) {
                val pct = (s.total / s.limite).coerceIn(0.0, 1.0).toFloat()
                val cor = when {
                    pct < 0.7f -> CorPositiva
                    pct < 1f -> CorAlerta
                    else -> CorNegativa
                }
                LinearProgressIndicator(progress = { pct }, color = cor, modifier = Modifier.fillMaxWidth().height(8.dp))
                Text(
                    if (s.total > s.limite) "Passou ${reais(s.total - s.limite)} do limite de ${reais(s.limite)}"
                    else "Restam ${reais(s.restante ?: 0.0)} de ${reais(s.limite)}",
                    color = cor,
                )
            } else {
                Text("Sem limite definido", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (carregando) LinearProgressIndicator(Modifier.fillMaxWidth().height(2.dp))
        }
    }
}

@Composable
private fun CompraCartao(compra: Compra, aoEditar: (Linha) -> Unit) {
    var aberto by rememberSaveable(compra.chave ?: compra.linhas.firstOrNull()?.id) { mutableStateOf(false) }
    val unica = compra.linhas.singleOrNull()
    val temDetalhe = compra.cupom && compra.categorias.any { it.itens.isNotEmpty() || compra.categorias.size > 1 }
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer),
        shape = RoundedCornerShape(14.dp),
        modifier = Modifier.fillMaxWidth().clickable {
            if (temDetalhe) aberto = !aberto else unica?.let(aoEditar)
        },
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text((if (compra.cupom) "🧾 " else "") + compra.nome, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    val meta = buildList {
                        if (temDetalhe) {
                            add("${compra.categorias.size} categoria" + if (compra.categorias.size > 1) "s" else "")
                            compra.categorias.sumOf { it.itens.size }.takeIf { it > 0 }?.let { add("$it itens") }
                        } else {
                            unica?.categoria?.let(::add)
                        }
                        if (compra.itensPendentes) add("itens pendentes")
                        add(compra.formaPagamento)
                        compra.lancadoPor.takeIf { it.isNotBlank() }?.let(::add)
                    }.joinToString(" · ")
                    Text(meta, fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
                }
                Text(reais(compra.total), fontWeight = FontWeight.SemiBold,
                    color = if (compra.total < 0) CorPositiva else MaterialTheme.colorScheme.onSurface)
            }
            if (aberto) {
                HorizontalDivider(Modifier.padding(vertical = 10.dp), color = MaterialTheme.colorScheme.outline)
                compra.categorias.forEach { cat ->
                    val linha = compra.linhas.firstOrNull { it.id == cat.id }
                    Row(Modifier.fillMaxWidth().clickable { linha?.let(aoEditar) }.padding(vertical = 4.dp)) {
                        Text(cat.categoria, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
                        Text(reais(cat.valor), fontWeight = FontWeight.Medium)
                    }
                    cat.itens.forEach { p ->
                        Row(Modifier.fillMaxWidth().padding(start = 12.dp, top = 2.dp, bottom = 2.dp)) {
                            Text(quantidade(p.quantidade, p.unidade) + p.descricao, fontSize = 13.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f))
                            Text(reais(p.valor), fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Resumo(resumo: List<FatiaResumo>) {
    Bloco {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            resumo.forEach { f ->
                Column {
                    Row {
                        Text(f.categoria, modifier = Modifier.weight(1f), fontSize = 14.sp)
                        Text("${reais(f.valor)} · ${f.pct.toString().replace(".", ",")}%", fontSize = 14.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Box(Modifier.fillMaxWidth().height(4.dp).background(MaterialTheme.colorScheme.outline, RoundedCornerShape(2.dp))) {
                        Box(Modifier.fillMaxWidth((f.pct / 100).toFloat().coerceIn(0f, 1f)).height(4.dp)
                            .background(MaterialTheme.colorScheme.primary, RoundedCornerShape(2.dp)))
                    }
                }
            }
        }
    }
}

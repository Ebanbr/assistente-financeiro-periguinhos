package br.periguinhos.semana

import android.widget.Toast
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import org.json.JSONObject
import kotlin.math.abs

/** Cupom lido pelo QR: confere as categorias dos itens e lança; nota offline lança só com o total. */
@Composable
fun CupomTela(api: Api, opcoes: Opcoes, leitura: JSONObject, link: String, aoSair: (Boolean) -> Unit) {
    val contexto = LocalContext.current
    val escopo = rememberCoroutineScope()
    val status = leitura.optString("status")
    val chave = leitura.optString("chave")
    val total = leitura.optDouble("total", 0.0)
    val jaLancado = leitura.optBoolean("ja_lancado")
    var estab by remember { mutableStateOf(leitura.optString("estabelecimento", "").let { if (it == "null") "" else it }) }
    var forma by remember {
        mutableStateOf(leitura.optString("forma_pagamento").takeIf { it in opcoes.formas })
    }
    var cartao by remember {
        mutableStateOf(leitura.optString("banco").takeIf { it in opcoes.cartoes } ?: opcoes.cartoes.firstOrNull())
    }
    var categoriaTotal by remember { mutableStateOf<String?>("🛒 Supermercado".takeIf { it in opcoes.categorias }) }
    val itens = remember { mutableStateListOf<ItemCupom>().apply { addAll(itensDoCupom(leitura)) } }
    var editando by remember { mutableStateOf<Int?>(null) }
    var salvando by remember { mutableStateOf(false) }
    var erro by remember { mutableStateOf<String?>(null) }

    fun enviar() {
        erro = when {
            estab.isBlank() -> "Informe o estabelecimento."
            forma == null -> "Escolha a forma de pagamento."
            forma == "💳 Crédito" && cartao == null -> "Escolha o cartão."
            status != "ok" && categoriaTotal == null -> "Escolha a categoria."
            else -> null
        }
        if (erro != null) return
        salvando = true
        escopo.launch {
            try {
                val pedido = JSONObject().put("link", link).put("estabelecimento", estab.trim())
                    .put("forma_pagamento", forma).put("banco", if (forma == "💳 Crédito") cartao else "")
                if (status == "ok") {
                    val cats = JSONObject()
                    itens.forEach { cats.put(it.item.toString(), it.categoria) }
                    api.lancarCupom(pedido.put("chave", chave).put("categorias", cats))
                    Toast.makeText(contexto, "Cupom lançado: ${estab.trim()} · ${reais(total)}", Toast.LENGTH_SHORT).show()
                } else {
                    api.lancarSoTotal(pedido.put("categoria", categoriaTotal))
                    Toast.makeText(contexto, "Lançado só com o total (itens pendentes)", Toast.LENGTH_SHORT).show()
                }
                aoSair(true)
            } catch (e: ApiErro) {
                erro = e.message
            } finally {
                salvando = false
            }
        }
    }

    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
                IconButton(onClick = { aoSair(false) }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Voltar") }
                Column(Modifier.weight(1f)) {
                    Text("🧾 Cupom fiscal", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
                    Text("${dataBr(leitura.optString("data"))} · ${reais(total)}" +
                        if (status == "ok") " · ${itens.size} itens" else "",
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        if (jaLancado) {
            item {
                Bloco {
                    Text(if (status == "pendente") "Esse cupom já está lançado. Quando a SEFAZ receber a nota, leia o " +
                        "QR Code de novo para trocar o total pela divisão por categoria." else "Esse cupom já foi lançado.")
                }
            }
            return@LazyColumn
        }
        when (status) {
            "pendente" -> item {
                Bloco {
                    Text("A SEFAZ ainda não recebeu essa nota (o caixa estava offline). Lance agora só com o total e, " +
                        "quando ela chegar (até 24 h), toque em \"Já chegou?\" na semana para dividir por categoria.")
                }
            }
            "sem_itens" -> item {
                Bloco { Text(leitura.optString("mensagem") + " Dá para lançar só com o total.") }
            }
        }
        item {
            OutlinedTextField(estab, { estab = it }, label = { Text("Estabelecimento") }, singleLine = true,
                modifier = Modifier.fillMaxWidth())
        }
        item {
            Text("Forma de pagamento", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Escolha(opcoes.formas, forma) { forma = it }
            if (forma == "💳 Crédito") {
                Spacer(Modifier.height(8.dp))
                Text("Cartão", color = MaterialTheme.colorScheme.onSurfaceVariant)
                Escolha(opcoes.cartoes, cartao) { cartao = it }
            }
        }
        if (status == "ok") {
            item {
                val porCat = itens.groupBy { it.categoria }.mapValues { (_, l) -> l.sumOf { it.valor } }
                    .toList().sortedByDescending { it.second }
                Bloco {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        porCat.forEach { (cat, v) ->
                            Row { Text(cat, Modifier.weight(1f)); Text(reais(v), fontWeight = FontWeight.Medium) }
                        }
                        val soma = porCat.sumOf { it.second }
                        if (abs(soma - total) >= 1.0) {
                            Text("A soma dos itens (${reais(soma)}) não bate com o total da nota.", color = CorAlerta,
                                fontSize = 13.sp)
                        }
                    }
                }
                Text("Toque num item para trocar a categoria.", fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp))
            }
            itemsIndexed(itens, key = { _, it -> it.item }) { i, it ->
                Column(Modifier.fillMaxWidth().clickable { editando = i }.padding(vertical = 6.dp)) {
                    Row {
                        Text(quantidade(it.quantidade, it.unidade) + it.descricao, Modifier.weight(1f), maxLines = 2,
                            overflow = TextOverflow.Ellipsis)
                        Text(reais(it.valor))
                    }
                    Text(it.categoria, fontSize = 13.sp, color = MaterialTheme.colorScheme.primary)
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outline)
            }
        } else {
            item { CampoCategoria("Categoria", categoriaTotal, opcoes.categorias, { categoriaTotal = it }) }
        }
        item {
            erro?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(onClick = ::enviar, enabled = !salvando, modifier = Modifier.fillMaxWidth().height(52.dp)) {
                Text(when {
                    salvando -> "Lançando…"
                    status == "ok" && leitura.optBoolean("substitui_total") -> "💾 Trocar o total pela divisão"
                    status == "ok" -> "💾 Lançar cupom"
                    else -> "⚡ Lançar só com o total (${reais(total)})"
                })
            }
            Spacer(Modifier.height(32.dp))
        }
    }

    editando?.let { i ->
        EscolherCategoria(opcoes.categoriasCupom, { editando = null }) { cat ->
            itens[i] = itens[i].copy(categoria = cat)
            editando = null
        }
    }
}

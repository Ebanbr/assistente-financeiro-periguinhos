package br.periguinhos.semana

import android.widget.Toast
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SelectableDates
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

/** Lançar um gasto novo (linha == null) ou editar/excluir um lançado à mão. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GastoTela(api: Api, opcoes: Opcoes, linha: Linha?, aoSair: (Boolean) -> Unit) {
    val contexto = LocalContext.current
    val escopo = rememberCoroutineScope()
    var descricao by remember { mutableStateOf(linha?.descricao ?: "") }
    var valor by remember { mutableStateOf(linha?.valor?.let { "%.2f".format(it).replace(".", ",") } ?: "") }
    var data by remember { mutableStateOf(linha?.data?.let { runCatching { LocalDate.parse(it) }.getOrNull() } ?: LocalDate.now()) }
    var categoria by remember { mutableStateOf(linha?.categoria?.takeIf { it.isNotBlank() }) }
    var sugerida by remember { mutableStateOf<String?>(null) }
    var forma by remember { mutableStateOf(linha?.formaPagamento?.takeIf { it in opcoes.formas } ?: "💳 Crédito") }
    var cartao by remember { mutableStateOf(linha?.banco?.takeIf { it in opcoes.cartoes } ?: opcoes.cartoes.firstOrNull()) }
    var escolherData by remember { mutableStateOf(false) }
    var confirmarExclusao by remember { mutableStateOf(false) }
    var salvando by remember { mutableStateOf(false) }
    var erro by remember { mutableStateOf<String?>(null) }

    fun sugerir() {
        val d = descricao.trim()
        if (d.isEmpty() || linha != null) return
        escopo.launch {
            runCatching { api.sugestao(d) }.getOrNull()?.let { s ->
                // só preenche se está vazio ou ainda com a sugestão anterior: nunca passa por cima da escolha
                if (categoria == null || categoria == sugerida) categoria = s
                sugerida = s
            }
        }
    }

    fun salvar() {
        val v = lerValor(valor)
        erro = when {
            descricao.isBlank() -> "Informe a descrição."
            v == null || v == 0.0 -> "Informe o valor (estorno entra negativo)."
            categoria == null -> "Escolha a categoria."
            forma == "💳 Crédito" && cartao == null -> "Escolha o cartão."
            else -> null
        }
        if (erro != null) return
        salvando = true
        escopo.launch {
            try {
                api.salvarGasto(linha?.id, JSONObject()
                    .put("data", data.toString()).put("descricao", descricao.trim()).put("categoria", categoria)
                    .put("valor", v).put("forma_pagamento", forma).put("banco", if (forma == "💳 Crédito") cartao else ""))
                Toast.makeText(contexto, if (linha == null) "Gasto lançado: ${reais(v!!)}" else "Gasto atualizado",
                    Toast.LENGTH_SHORT).show()
                aoSair(true)
            } catch (e: ApiErro) {
                erro = e.message
            } finally {
                salvando = false
            }
        }
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { aoSair(false) }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Voltar") }
            Text(if (linha == null) "Novo gasto" else "Editar gasto", fontSize = 20.sp, fontWeight = FontWeight.SemiBold,
                modifier = Modifier.weight(1f))
            if (linha != null) {
                IconButton(onClick = { confirmarExclusao = true }) {
                    Icon(Icons.Default.Delete, "Excluir", tint = MaterialTheme.colorScheme.error)
                }
            }
        }
        OutlinedTextField(
            descricao, { descricao = it }, label = { Text("Descrição") }, singleLine = true,
            placeholder = { Text("ex: Padaria Cidade Jardim") },
            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Words),
            modifier = Modifier.fillMaxWidth().onFocusChanged { if (!it.isFocused) sugerir() },
        )
        OutlinedTextField(
            valor, { valor = it }, label = { Text("Valor (R$)") }, singleLine = true, placeholder = { Text("0,00") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            modifier = Modifier.fillMaxWidth(),
        )
        CampoCategoria("Categoria", categoria, opcoes.categorias, { categoria = it })
        sugerida?.takeIf { it == categoria }?.let {
            Text("Categoria lembrada deste lugar. Dá para trocar.", fontSize = 13.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text("Data: ${dataBr(data.toString())}", modifier = Modifier.clickable { escolherData = true }.padding(vertical = 8.dp),
            color = MaterialTheme.colorScheme.primary)
        Text("Forma de pagamento", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Escolha(opcoes.formas, forma) { forma = it }
        if (forma == "💳 Crédito") {
            Text("Cartão", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Escolha(opcoes.cartoes, cartao) { cartao = it }
        }
        erro?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(onClick = ::salvar, enabled = !salvando, modifier = Modifier.fillMaxWidth().height(52.dp)) {
            Text(if (salvando) "Salvando…" else if (linha == null) "💾 Lançar gasto" else "💾 Salvar")
        }
    }

    if (escolherData) {
        val hojeMs = LocalDate.now().atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli()
        val estado = rememberDatePickerState(
            initialSelectedDateMillis = data.atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli(),
            selectableDates = object : SelectableDates {
                override fun isSelectableDate(utcTimeMillis: Long) = utcTimeMillis <= hojeMs
            },
        )
        DatePickerDialog(
            onDismissRequest = { escolherData = false },
            confirmButton = {
                TextButton(onClick = {
                    estado.selectedDateMillis?.let { data = Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate() }
                    escolherData = false
                }) { Text("OK") }
            },
            dismissButton = { TextButton(onClick = { escolherData = false }) { Text("Cancelar") } },
        ) { DatePicker(estado) }
    }

    if (confirmarExclusao && linha != null) {
        AlertDialog(
            onDismissRequest = { confirmarExclusao = false },
            title = { Text("Excluir gasto?") },
            text = { Text("${linha.descricao} · ${reais(linha.valor)}") },
            confirmButton = {
                TextButton(onClick = {
                    confirmarExclusao = false
                    escopo.launch {
                        try {
                            api.excluirGasto(linha.id)
                            Toast.makeText(contexto, "Gasto excluído", Toast.LENGTH_SHORT).show()
                            aoSair(true)
                        } catch (e: ApiErro) {
                            erro = e.message
                        }
                    }
                }) { Text("Excluir", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { confirmarExclusao = false }) { Text("Cancelar") } },
        )
    }
}

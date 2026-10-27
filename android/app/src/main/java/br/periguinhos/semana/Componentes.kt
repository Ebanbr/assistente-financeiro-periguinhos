package br.periguinhos.semana

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import java.text.Normalizer

val CorPositiva = Color(0xFF34D399)
val CorAlerta = Color(0xFFFBBF24)
val CorNegativa = Color(0xFFF87171)

private val Cores: ColorScheme = darkColorScheme(
    primary = Color(0xFF7DD3FC),
    onPrimary = Color(0xFF0B1220),
    secondary = Color(0xFF93C5FD),
    background = Color(0xFF0B1220),
    onBackground = Color(0xFFEAF1FF),
    surface = Color(0xFF0B1220),
    onSurface = Color(0xFFEAF1FF),
    surfaceVariant = Color(0xFF131C2E),
    onSurfaceVariant = Color(0xFFA9B6CC),
    surfaceContainer = Color(0xFF131C2E),
    surfaceContainerHigh = Color(0xFF18233A),
    surfaceContainerHighest = Color(0xFF1E2A44),
    outline = Color(0xFF2B3A55),
    error = CorNegativa,
)

@Composable
fun Tema(conteudo: @Composable () -> Unit) = MaterialTheme(colorScheme = Cores, content = conteudo)

private fun semAcento(s: String) =
    Normalizer.normalize(s, Normalizer.Form.NFD).replace(Regex("\\p{M}+"), "").lowercase()

/** Campo que abre a lista de categorias com busca (são quase 100). */
@Composable
fun CampoCategoria(rotulo: String, atual: String?, opcoes: List<String>, aoEscolher: (String) -> Unit,
                   modifier: Modifier = Modifier) {
    var aberto by remember { mutableStateOf(false) }
    Row(
        modifier.fillMaxWidth().clickable { aberto = true }
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        OutlinedTextField(
            value = atual ?: "", onValueChange = {}, readOnly = true, enabled = false,
            label = { Text(rotulo) }, placeholder = { Text("Escolha a categoria") },
            trailingIcon = { Icon(Icons.Default.ArrowDropDown, null) },
            modifier = Modifier.fillMaxWidth(),
            colors = androidx.compose.material3.OutlinedTextFieldDefaults.colors(
                disabledTextColor = MaterialTheme.colorScheme.onSurface,
                disabledBorderColor = MaterialTheme.colorScheme.outline,
                disabledLabelColor = MaterialTheme.colorScheme.onSurfaceVariant,
                disabledPlaceholderColor = MaterialTheme.colorScheme.onSurfaceVariant,
                disabledTrailingIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
            ),
        )
    }
    if (aberto) EscolherCategoria(opcoes, { aberto = false }) { aoEscolher(it); aberto = false }
}

@Composable
fun EscolherCategoria(opcoes: List<String>, aoFechar: () -> Unit, aoEscolher: (String) -> Unit) {
    var busca by remember { mutableStateOf("") }
    val filtradas = remember(busca, opcoes) {
        val b = semAcento(busca.trim())
        if (b.isEmpty()) opcoes else opcoes.filter { semAcento(it).contains(b) }
    }
    AlertDialog(
        onDismissRequest = aoFechar,
        confirmButton = {},
        dismissButton = { TextButton(onClick = aoFechar) { Text("Cancelar") } },
        title = { Text("Categoria") },
        text = {
            androidx.compose.foundation.layout.Column {
                OutlinedTextField(busca, { busca = it }, label = { Text("Buscar") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth())
                LazyColumn(Modifier.heightIn(max = 420.dp).padding(top = 8.dp)) {
                    items(filtradas) { cat ->
                        Text(cat, Modifier.fillMaxWidth().clickable { aoEscolher(cat) }.padding(vertical = 12.dp))
                        HorizontalDivider(color = MaterialTheme.colorScheme.outline)
                    }
                }
            }
        },
    )
}

/** Uma escolha entre poucas opções (forma de pagamento, cartão). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun Escolha(opcoes: List<String>, atual: String?, aoEscolher: (String) -> Unit) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        opcoes.forEach { op ->
            FilterChip(selected = op == atual, onClick = { aoEscolher(op) }, label = { Text(op) })
        }
    }
}

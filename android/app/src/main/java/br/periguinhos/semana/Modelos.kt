package br.periguinhos.semana

import org.json.JSONArray
import org.json.JSONObject
import java.text.NumberFormat
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

private val REAIS: NumberFormat = NumberFormat.getCurrencyInstance(Locale("pt", "BR"))
private val DIA_MES: DateTimeFormatter = DateTimeFormatter.ofPattern("dd/MM")
private val DATA_BR: DateTimeFormatter = DateTimeFormatter.ofPattern("dd/MM/yyyy")

fun reais(v: Double): String = REAIS.format(v).replace(" ", " ")
fun diaMes(iso: String): String = runCatching { LocalDate.parse(iso).format(DIA_MES) }.getOrDefault(iso)
fun dataBr(iso: String): String = runCatching { LocalDate.parse(iso).format(DATA_BR) }.getOrDefault(iso)

/** "12,50" / "12.50" / "1.234,56" → 12.5 (null se não for número). */
fun lerValor(texto: String): Double? {
    val t = texto.trim().replace("R$", "").replace(" ", "")
    val normal = if (t.contains(",")) t.replace(".", "").replace(",", ".") else t
    return normal.toDoubleOrNull()
}

private fun JSONObject.texto(nome: String): String = if (isNull(nome)) "" else optString(nome, "")
private fun <T> JSONArray?.lista(f: (JSONObject) -> T): List<T> =
    if (this == null) emptyList() else (0 until length()).map { f(getJSONObject(it)) }
private fun JSONArray?.textos(): List<String> =
    if (this == null) emptyList() else (0 until length()).map { getString(it) }

data class Opcoes(
    val categorias: List<String>,
    val categoriasCupom: List<String>,
    val formas: List<String>,
    val cartoes: List<String>,
) {
    companion object {
        fun de(j: JSONObject) = Opcoes(
            j.optJSONArray("categorias").textos(), j.optJSONArray("categorias_cupom").textos(),
            j.optJSONArray("formas").textos(), j.optJSONArray("cartoes").textos(),
        )
    }
}

data class Linha(
    val id: String, val data: String, val descricao: String, val categoria: String, val valor: Double,
    val formaPagamento: String, val banco: String, val observacao: String, val lancadoPor: String,
) {
    companion object {
        fun de(j: JSONObject) = Linha(
            j.texto("id"), j.texto("data"), j.texto("descricao"), j.texto("categoria"), j.optDouble("valor", 0.0),
            j.texto("forma_pagamento"), j.texto("banco"), j.texto("observacao"), j.texto("lancado_por"),
        )
    }
}

data class Produto(val descricao: String, val quantidade: Double, val unidade: String, val valor: Double)

data class CategoriaCompra(val id: String, val categoria: String, val valor: Double, val itens: List<Produto>)

data class Compra(
    val chave: String?, val nome: String, val total: Double, val cupom: Boolean, val itensPendentes: Boolean,
    val formaPagamento: String, val lancadoPor: String, val linhas: List<Linha>, val categorias: List<CategoriaCompra>,
) {
    companion object {
        fun de(j: JSONObject) = Compra(
            j.texto("chave").ifBlank { null }, j.texto("nome"), j.optDouble("total", 0.0), j.optBoolean("cupom"),
            j.optBoolean("itens_pendentes"), j.texto("forma_pagamento"), j.texto("lancado_por"),
            j.optJSONArray("linhas").lista(Linha::de),
            j.optJSONArray("categorias").lista { c ->
                CategoriaCompra(c.texto("id"), c.texto("categoria"), c.optDouble("valor", 0.0),
                    c.optJSONArray("itens").lista { p ->
                        Produto(p.texto("descricao"), p.optDouble("quantidade", 1.0), p.texto("unidade"),
                            p.optDouble("valor", 0.0))
                    })
            },
        )
    }
}

data class Dia(val data: String, val nome: String, val total: Double, val compras: List<Compra>)

data class FatiaResumo(val categoria: String, val valor: Double, val pct: Double)

data class Semana(
    val inicio: String, val fim: String, val recortada: Boolean, val encerrada: Boolean,
    val limite: Double, val total: Double, val restante: Double?, val dias: List<Dia>, val resumo: List<FatiaResumo>,
) {
    companion object {
        fun de(j: JSONObject) = Semana(
            j.texto("inicio"), j.texto("fim"), j.optBoolean("recortada"), j.optBoolean("encerrada"),
            j.optDouble("limite", 0.0), j.optDouble("total", 0.0),
            if (j.isNull("restante")) null else j.optDouble("restante"),
            j.optJSONArray("dias").lista { d ->
                Dia(d.texto("data"), d.texto("nome"), d.optDouble("total", 0.0), d.optJSONArray("compras").lista(Compra::de))
            },
            j.optJSONArray("resumo").lista { r -> FatiaResumo(r.texto("categoria"), r.optDouble("valor"), r.optDouble("pct")) },
        )
    }
}

data class CupomEsperando(val chave: String, val link: String, val data: String, val estabelecimento: String, val valor: Double) {
    companion object {
        fun de(j: JSONObject) = CupomEsperando(
            j.texto("chave"), j.texto("link"), j.texto("data"), j.texto("estabelecimento"), j.optDouble("valor", 0.0))
    }
}

/** Item do cupom lido, com a categoria que dá para trocar antes de lançar. */
data class ItemCupom(
    val item: Int, val descricao: String, val quantidade: Double, val unidade: String, val valor: Double,
    val categoria: String,
)

fun itensDoCupom(j: JSONObject): List<ItemCupom> = j.optJSONArray("itens").lista { i ->
    ItemCupom(i.optInt("item"), i.texto("descricao"), i.optDouble("quantidade", 1.0), i.texto("unidade"),
        i.optDouble("valor", 0.0), i.texto("categoria"))
}

fun quantidade(q: Double, unidade: String): String =
    if (q == 1.0) "" else (if (q % 1.0 == 0.0) q.toLong().toString() else q.toString().replace(".", ",")) +
        " ${unidade.lowercase()} · "

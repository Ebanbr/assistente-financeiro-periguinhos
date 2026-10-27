"""Leitor de QR Code ao vivo: abre a câmera traseira no navegador e devolve o texto assim que o QR aparece.

Usa st.components.v2 (Streamlit >= 1.51). No Chrome do Android o reconhecimento é o nativo do navegador
(BarcodeDetector); onde ele não existe (ex.: Chrome no Windows), carrega o jsQR do CDN.
"""
import streamlit as st

_CSS = """
.qr-box{position:relative;width:100%;max-width:520px;margin:0 auto}
.qr-box video{width:100%;border-radius:12px;background:#000;display:block}
.qr-mira{position:absolute;inset:18%;border:3px solid rgba(255,255,255,.85);border-radius:14px;
  box-shadow:0 0 0 999px rgba(0,0,0,.25);pointer-events:none}
.qr-status{font:14px/1.4 sans-serif;color:var(--st-text-color, #EAF1FF);text-align:center;margin:8px 0 2px}
"""

_HTML = """
<div class="qr-box"><video playsinline muted></video><div class="qr-mira"></div></div>
<div class="qr-status">Abrindo a câmera…</div>
"""

_JS = """
export default function (component) {
  const { parentElement, setTriggerValue } = component;
  const video = parentElement.querySelector("video");
  const status = parentElement.querySelector(".qr-status");
  let stream = null, parado = false, timer = null;

  const parar = () => {
    parado = true;
    if (timer) clearTimeout(timer);
    if (stream) stream.getTracks().forEach((t) => t.stop());
  };

  const carregarJsQR = () => new Promise((ok, erro) => {
    if (window.jsQR) return ok(window.jsQR);
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js";
    s.onload = () => ok(window.jsQR);
    s.onerror = erro;
    document.head.appendChild(s);
  });

  const achou = (texto) => {
    if (parado || !texto) return;
    parar();
    status.textContent = "✅ QR Code lido! Consultando a SEFAZ…";
    setTriggerValue("qr", texto);
  };

  (async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      status.textContent = "Este navegador não libera a câmera aqui. Use a foto ou cole o link.";
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      });
    } catch (e) {
      status.textContent = "Não consegui abrir a câmera (permissão negada?). Use a foto ou cole o link.";
      return;
    }
    if (parado) { parar(); return; }
    video.srcObject = stream;
    await video.play().catch(() => {});
    status.textContent = "Aponte para o QR Code do cupom";

    let detectar = null;
    if ("BarcodeDetector" in window) {
      try {
        const formatos = await window.BarcodeDetector.getSupportedFormats();
        if (formatos.includes("qr_code")) {
          const det = new window.BarcodeDetector({ formats: ["qr_code"] });
          detectar = async () => {
            const achados = await det.detect(video);
            return achados.length ? achados[0].rawValue : null;
          };
        }
      } catch (e) { detectar = null; }
    }
    if (!detectar) {
      try {
        const jsQR = await carregarJsQR();
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        detectar = async () => {
          const w = video.videoWidth, h = video.videoHeight;
          if (!w || !h) return null;
          const escala = Math.min(1, 1280 / Math.max(w, h));
          canvas.width = Math.round(w * escala); canvas.height = Math.round(h * escala);
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const r = jsQR(img.data, img.width, img.height, { inversionAttempts: "dontInvert" });
          return r ? r.data : null;
        };
      } catch (e) {
        status.textContent = "Não consegui carregar o leitor de QR. Use a foto ou cole o link.";
        return;
      }
    }

    const ciclo = async () => {
      if (parado) return;
      try { achou(await detectar()); } catch (e) { /* quadro ainda sem imagem */ }
      if (!parado) timer = setTimeout(ciclo, 200);
    };
    ciclo();
  })();

  return parar;
}
"""

try:  # Streamlit < 1.51 não tem components.v2: a página cai na foto/link
    import streamlit.components.v2 as _v2
    _componente = _v2.component("leitor_qr_cupom", html=_HTML, css=_CSS, js=_JS)
except (ImportError, AttributeError):
    _componente = None


def leitor_disponivel():
    return _componente is not None


def ler_qr_ao_vivo(key="leitor_qr"):
    """Mostra a câmera ao vivo; devolve o texto do QR no rerun em que ele foi lido (senão None)."""
    if _componente is None:
        return None
    resultado = _componente(key=key, on_qr_change=lambda: None)
    return getattr(resultado, "qr", None) or None

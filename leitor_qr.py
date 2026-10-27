"""Leitor de QR Code ao vivo: abre a câmera traseira no navegador e devolve o texto assim que o QR aparece.

Usa st.components.v2 (Streamlit >= 1.51). No Chrome do Android o reconhecimento é o nativo do navegador
(BarcodeDetector) e, junto, o jsQR do CDN no recorte do quadro; pede foco contínuo e zoom 2x quando dá.
"""
import streamlit as st

_CSS = """
.qr-box{position:relative;width:100%;max-width:520px;margin:0 auto}
.qr-box video{width:100%;border-radius:12px;background:#000;display:block;cursor:pointer}
.qr-mira{position:absolute;inset:10%;border:3px solid rgba(255,255,255,.85);border-radius:14px;
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
  let stream = null, track = null, parado = false, timer = null, quadros = 0;

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

  // foco contínuo e um pouco de zoom: dá para segurar mais longe, onde a câmera consegue focar
  const ajustarCamera = async () => {
    if (!track || !track.getCapabilities) return "";
    const caps = track.getCapabilities();
    const extra = [];
    try {
      if (caps.focusMode && caps.focusMode.includes("continuous")) {
        await track.applyConstraints({ advanced: [{ focusMode: "continuous" }] });
        extra.push("foco auto");
      }
    } catch (e) {}
    try {
      if (caps.zoom && caps.zoom.max >= 1.5) {
        const z = Math.min(caps.zoom.max, Math.max(caps.zoom.min || 1, 2));
        await track.applyConstraints({ advanced: [{ zoom: z }] });
        extra.push("zoom " + z + "x");
      }
    } catch (e) {}
    return extra.join(", ");
  };

  video.addEventListener("click", async () => {  // tocar no vídeo = focar de novo
    if (!track || !track.getCapabilities) return;
    const modos = track.getCapabilities().focusMode || [];
    try {
      if (modos.includes("single-shot")) await track.applyConstraints({ advanced: [{ focusMode: "single-shot" }] });
      if (modos.includes("continuous")) await track.applyConstraints({ advanced: [{ focusMode: "continuous" }] });
    } catch (e) {}
  });

  (async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      status.textContent = "Este navegador não libera a câmera aqui. Use a foto ou cole o link.";
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 2560 }, height: { ideal: 1440 } },
        audio: false,
      });
    } catch (e) {
      status.textContent = "Não consegui abrir a câmera (permissão negada?). Use a foto ou cole o link.";
      return;
    }
    if (parado) { parar(); return; }
    track = stream.getVideoTracks()[0];
    video.srcObject = stream;
    await video.play().catch(() => {});
    const ajustes = await ajustarCamera();

    // leitor nativo do navegador (Chrome Android) no quadro inteiro
    let nativo = null;
    if ("BarcodeDetector" in window) {
      try {
        const formatos = await window.BarcodeDetector.getSupportedFormats();
        if (formatos.includes("qr_code")) {
          const det = new window.BarcodeDetector({ formats: ["qr_code"] });
          nativo = async () => {
            const achados = await det.detect(video);
            return achados.length ? achados[0].rawValue : null;
          };
        }
      } catch (e) { nativo = null; }
    }
    // jsQR no recorte do quadro branco (o QR ocupa mais pixels ali)
    let reserva = null;
    try {
      const jsQR = await carregarJsQR();
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      reserva = async () => {
        const w = video.videoWidth, h = video.videoHeight;
        if (!w || !h) return null;
        const lado = Math.round(Math.min(w, h) * 0.8);
        const sx = Math.round((w - lado) / 2), sy = Math.round((h - lado) / 2);
        const alvo = Math.min(lado, 1000);
        canvas.width = alvo; canvas.height = alvo;
        ctx.drawImage(video, sx, sy, lado, lado, 0, 0, alvo, alvo);
        const img = ctx.getImageData(0, 0, alvo, alvo);
        const r = jsQR(img.data, alvo, alvo, { inversionAttempts: "attemptBoth" });
        return r ? r.data : null;
      };
    } catch (e) { reserva = null; }

    if (!nativo && !reserva) {
      status.textContent = "Não consegui carregar o leitor de QR. Use a foto ou cole o link.";
      return;
    }
    const motores = [nativo && "nativo", reserva && "jsQR"].filter(Boolean).join(" + ");
    const info = () => `Aponte para o QR Code · toque no vídeo para focar` +
      ` (${motores} · ${video.videoWidth}×${video.videoHeight}${ajustes ? " · " + ajustes : ""} · ${quadros} quadros)`;
    status.textContent = info();

    const ciclo = async () => {
      if (parado) return;
      quadros += 1;
      try { if (nativo) achou(await nativo()); } catch (e) {}
      try { if (!parado && reserva) achou(await reserva()); } catch (e) {}
      if (!parado) {
        if (quadros % 5 === 0) status.textContent = info();
        timer = setTimeout(ciclo, 150);
      }
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

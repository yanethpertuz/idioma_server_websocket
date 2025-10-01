import os
import asyncio
import websockets
import io
import speech_recognition as sr
from googletrans import Translator
from gtts import gTTS
import logging

# Configurar logging para ver mensajes en Render
logging.basicConfig(level=logging.INFO)

# --- INICIALIZACIÓN DE HERRAMIENTAS ---
# Estas herramientas son pesadas, así que las inicializamos una sola vez.
r = sr.Recognizer()
translator = Translator()

# Un conjunto (set) para mantener a todos los clientes conectados.
# Usamos un set porque es más eficiente para añadir y quitar.
CONNECTED_CLIENTS = set()

# --- FUNCIONES DE LÓGICA (Tu código original, sin cambios) ---
def traducir_audio_stream(audio_bytes):
    lang_codes = (('en-US', 'en'), ('es-ES', 'es'))
    lang1_stt, lang1_tts = lang_codes[0]
    lang2_stt, lang2_tts = lang_codes[1]

    try:
        # Asumimos que el audio viene en formato WAV crudo
        audio_data = sr.AudioData(audio_bytes, sample_rate=44100, sample_width=2)
        
        texto_detectado = ""
        try:
            texto_detectado = r.recognize_google(audio_data, language=lang1_stt)
        except sr.UnknownValueError:
            try:
                texto_detectado = r.recognize_google(audio_data, language=lang2_stt)
            except sr.UnknownValueError:
                logging.info("-> No se pudo entender el audio.")
                return None
        
        if not texto_detectado:
            return None

        logging.info(f"-> Detectado: '{texto_detectado}'")

        detected_lang_obj = translator.detect(texto_detectado)
        if detected_lang_obj:
            detected_lang = detected_lang_obj.lang
            destino_tts = lang2_tts if detected_lang == lang1_tts else lang1_tts
            
            texto_traducido = translator.translate(texto_detectado, dest=destino_tts).text
            logging.info(f"-> Traducido a ({destino_tts}): '{texto_traducido}'")

            fp = io.BytesIO()
            gTTS(text=texto_traducido, lang=destino_tts).write_to_fp(fp)
            fp.seek(0)
            return fp.read()
        else:
            logging.info("-> No se pudo detectar el idioma del texto.")
            return None
    except Exception as e:
        logging.error(f"!! Error en el proceso de traducción: {e}")
        return None

# --- MANEJO DE WEBSOCKETS ---
async def handle_client(websocket, path):
    """
    Gestiona la conexión de un cliente WebSocket.
    """
    logging.info(f"[NUEVA CONEXIÓN] Cliente conectado desde {websocket.remote_address}")
    CONNECTED_CLIENTS.add(websocket)
    
    try:
        # El bucle 'async for' espera a recibir mensajes del cliente.
        async for message in websocket:
            logging.info(f"-> Recibidos {len(message)} bytes de audio.")
            
            # El mensaje ya es el audio en bytes, no necesitamos recibir un header.
            translated_audio = traducir_audio_stream(message)
            
            if translated_audio:
                logging.info(f"-> Enviando {len(translated_audio)} bytes de audio traducido.")
                
                # Creamos una lista de tareas de envío para todos los OTROS clientes.
                tasks = []
                for client in CONNECTED_CLIENTS:
                    if client != websocket:
                        tasks.append(client.send(translated_audio))
                
                # Ejecutamos todas las tareas de envío en paralelo.
                await asyncio.gather(*tasks)

    except websockets.exceptions.ConnectionClosed as e:
        logging.info(f"[CONEXIÓN CERRADA] Cliente desconectado: {e}")
    finally:
        # Nos aseguramos de quitar al cliente del conjunto al desconectarse.
        CONNECTED_CLIENTS.remove(websocket)
        logging.info(f"Clientes activos: {len(CONNECTED_CLIENTS)}")

async def start_server():
    """ 
    Inicia el servidor WebSocket.
    """
    HOST = '0.0.0.0'
    PORT = int(os.environ.get('PORT', 8765)) # 8765 para pruebas locales

    # websockets.serve inicia el servidor de manera asíncrona
    async with websockets.serve(handle_client, HOST, PORT):
        logging.info(f"✅ [SERVIDOR WEBSOCKET INICIADO] Escuchando en {HOST}:{PORT}")
        # Mantiene el servidor corriendo indefinidamente
        await asyncio.Future()

if __name__ == "__main__":
    # asyncio.run() ejecuta la función asíncrona principal
    asyncio.run(start_server())

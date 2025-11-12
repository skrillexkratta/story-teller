import os
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
from PIL import Image
import requests
from io import BytesIO

# --- FÖRBEREDELSER ---
# Streamlit hanterar .env-laddning lite annorlunda vid deployment,
# men detta fungerar lokalt:
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    st.error("FEL: API-nyckeln hittades inte. Kontrollera din .env-fil.")
    st.stop() # Stoppar appen om nyckeln saknas

client = OpenAI(api_key=api_key)

# --- LOGIK FÖR AI-ANROP (Manuskrivare) ---
# Denna funktion är nästan identisk med den i gui_app.py
def generate_story_logic(genre, topic, length):
    if not topic.strip():
        return "Vänligen ange ett ämne."

    system_prompt = f"Du är en professionell manusförfattare. Skriv ett {length} filmmanus i genren {genre} med tydliga scenanvisningar, karaktärsbeskrivningar och dialoger. Fokusera på att skapa visuella scener."
    user_prompt = f"Ämne/idé: '{topic}'"
    
    if length == "kort":
        max_t = 200
    elif length == "mellanlång":
        max_t = 600
    else:
        max_t = 1200

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_t,
            temperature=0.8
        )
        return response.choices.message.content

    except Exception as e:
        return f"Ett fel uppstod: {e}"

# --- STREAMLIT WEBBGRÄNSSNITT ---

st.title("AI Story & Image Generator")

# Sidopanel för kontroller
with st.sidebar:
    st.header("Inställningar")
    genres = ["Fantasy", "Sci-Fi", "Deckare", "Romantik", "Komedi"]
    genre = st.selectbox("Välj Genre:", genres)
    
    lengths = ["kort", "mellanlång", "lång"]
    length = st.selectbox("Välj Längd:", lengths, index=1)

# Huvudlayout
topic = st.text_input("Ämne/Idé för manuset:")

if st.button("Generera Manus"):
    # Logik för att generera manus
    with st.spinner("AI skriver manus..."):
        story_content = generate_story_logic(genre, topic, length)
        st.session_state["story"] = story_content # Spara i session state för att behålla texten

# Visa det genererade manuset
if "story" in st.session_state:
    st.subheader("Genererat Manus:")
    st.markdown(st.session_state["story"])

    # Knapp för bildgenerering
    if st.button("Generera Bild från Markerad Text (Markera text i rutan ovan först)"):
        # Streamlit har inte inbyggd textmarkering som Tkinter.
        # Användaren måste kopiera och klistra in text till ett nytt fält för att detta ska fungera i webbversionen.
        # För enkelhetens skull, be användaren kopiera text manuellt från rutan ovan.
        st.warning("För bildgenerering, kopiera text från manuset ovan och klistra in i fältet nedan.")

        with st.form("image_form"):
            image_prompt = st.text_area("Klistra in scenbeskrivning här:", height=100)
            if st.form_submit_button("Generera Bild"):
                with st.spinner("Genererar bild med DALL-E..."):
                    try:
                        response = client.images.generate(
                            model="dall-e-2",
                            prompt=f"Skapa en realistisk illustration i filmstil av: {image_prompt}",
                            size="512x512",
                            quality="standard",
                            n=1,
                        )
                        image_url = response.data.url
                        
                        # Visa bilden direkt i webbappen
                        st.image(image_url, caption=image_prompt)
                        st.success("Bild genererad!")

                    except Exception as e:
                        st.error(f"Ett fel uppstod vid bildgenerering: {e}")


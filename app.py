import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import os  
import io
import json
import re
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

st.set_page_config(page_title="Face Recognition", layout="centered")
st.title(" Face Recognition & Anti-Spoof System")

# Define the response schema for structured output
response_schema = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "status": types.Schema(type=types.Type.STRING),
        "confidence_score": types.Schema(type=types.Type.INTEGER),
        "reasoning": types.Schema(type=types.Type.STRING),
    },
    required=["status", "confidence_score", "reasoning"]
)


KNOWN_FACES_DIR = "known_faces"
def prepare_image_for_api(image_path_or_pil):
    """Converts image to the byte format required by the new 2.x SDK."""
    if isinstance(image_path_or_pil, str):
        with open(image_path_or_pil, "rb") as f:
            return types.Part.from_bytes(data=f.read(), mime_type="image/jpeg")
    else:
        buf = io.BytesIO()
        image_path_or_pil.save(buf, format='JPEG')
        return types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")

def get_security_context():
    """Builds the gallery of authorized users."""
    parts = ["CONTEXT: These images represent authorized users allowed to access the system."]
    if os.path.exists(KNOWN_FACES_DIR):
        for person in os.listdir(KNOWN_FACES_DIR):
            p_dir = os.path.join(KNOWN_FACES_DIR, person)
            if os.path.isdir(p_dir):
                for img in os.listdir(p_dir):
                    if img.lower().endswith(('.jpg', '.png', '.jpeg')):
                        parts.append(f"NAME: {person}")
                        parts.append(prepare_image_for_api(os.path.join(p_dir, img)))
                        break
    return parts
# ... [keep prepare_image_for_api and get_security_context as is] ...

uploaded_file = st.file_uploader("Scan Face", type=["jpg", "png", "jpeg"])
if uploaded_file:
    pil_img = Image.open(uploaded_file)
    st.image(pil_img, caption="Live Feed", width=400)
    
    with st.spinner("Analyzing biometric data..."):
        test_part = prepare_image_for_api(pil_img)
        context = get_security_context()
        
        prompt_parts = [
            *context,
            "TASK: Analyze the final image for IDENTITY and SPOOFING.",
            test_part,
            """
            SECURITY PROTOCOL:
            1. Check for 'Photo-of-a-photo' or 'Screen-replay' artifacts.
            2. IDENTITY: Compare against known users.
            
            OUTPUT INSTRUCTIONS:
            - status: 'Match Found: [Name]', 'BLOCK: SPOOF', 'BLOCK: UNKNOWN', or 'BLOCK: NON_HUMAN'.
            - confidence_score: An integer 0-100 representing how certain you are of the identity match.
            - reasoning: Brief explanation of the score.
            """
        ]

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_parts,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                )
            )

            result_text = response.text.strip()
            
            # Parse JSON response
            result = json.loads(result_text)
            status = result.get("status", "BLOCK: UNKNOWN")
            score = result.get("confidence_score", 0)
            reasoning = result.get("reasoning", "")
            
            st.divider()

            # Displaying the Confidence Gauge
            col1, col2 = st.columns([3, 1])
            with col2:
                st.metric("Confidence", f"{score}%")
            
            with col1:
                if "Match Found" in status:
                    st.success(f"**Match Found Successfully:** {status}")
                    st.progress(score / 100)
                elif "SPOOF" in status:
                    st.error(f"**SECURITY ALERT:** {status} (Certainty: {score}%)")
                else:
                    st.warning(f"**Match Not Found:** {status}")
            
            st.info(f"**Analysis:** {reasoning}")

        except json.JSONDecodeError:
            st.error("Failed to parse response. Please try again.")
        except Exception as e:
            st.error(f"Error: {e}")

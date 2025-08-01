import streamlit as st
from typing import Optional, TypedDict
import os
from groq import Groq
from langgraph.graph import StateGraph, END

class ProspectMessageState(TypedDict):
    prospect_name: Optional[str]
    designation: Optional[str]
    company: Optional[str]
    industry: Optional[str]
    prospect_background: str
    final_message: Optional[str]

GROQ_API_KEY = st.secrets["GROQ_API_KEY"]    

client = Groq(api_key=GROQ_API_KEY)


def groq_llm(prompt: str, model: str = "llama3-8b-8192", temperature: float = 0.3) -> str:
    """Generate text using Groq API"""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()

def summarizer(text: str) -> str:
    """Summarize long backgrounds into key points"""
    if not text or not isinstance(text, str):
        return "No content to summarize."

    truncated_text = text[:4000]
    prompt = f"""
Create 3 concise bullet points from this background text. Focus on key professional highlights and achievements:

{truncated_text}

Bullet points:
-"""
    try:
        return groq_llm(prompt).strip()
    except Exception as e:
        print(f"Summarization error: {e}")
        return "Background summary unavailable"



def summarize_backgrounds(state: ProspectMessageState) -> ProspectMessageState:
    """Node to summarize prospect and user backgrounds"""
    return {
        **state,
        "prospect_background": summarizer(state["prospect_background"]),
        # "my_background": summarizer(state["my_background"])
    }

import re

def extract_name_from_background(background: str) -> str:
    if not background:
        return "there"
    # Take first two capitalized words as name
    match = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?', background)
    if match:
        return match[0]
    return "there"
def generate_message(state: ProspectMessageState) -> ProspectMessageState:
    """Node to generate LinkedIn message with event context"""
    extracted_name = extract_name_from_background(state['prospect_background'])
    prospect_first_name = extracted_name.split()[0] if extracted_name != "Unknown Prospect" else "there"
    my_name = "Joseph"  # Hardcoded for consistency
    prompt = f"""
IMPORTANT: Output ONLY the message itself. 
Do NOT include explanations, labels, or introductions.

Write a SHORT LinkedIn connection note (MAX 3 LINES, under 300 characters).  
Tone: professional, conversational, concise.

MANDATORY RULES:
1. Start with: "Hi {{first_name}},"
2. The SECOND LINE must begin with "Glad to be connected." (Do not skip this)
3. Then reference the prospect’s background (company, role, or focus) based on: {state['prospect_background']}
4. Pivot to a relevant banking workflow/operations discussion (e.g., lending, commercial loan process automation, digital banking, or regional banking strategies).
5. For the FOURTH LINE, dynamically craft a unique, concise sentence inviting a brief chat.  
   Style examples:  
   - "It would be great to have a chat sometime about how these trends are evolving in the industry."  
   - "Would love to hear your thoughts on how automation is shaping operations."  
   - "Are you open to a quick chat sometime?"  
   - "I'd love to exchange ideas on how technology is driving real change in mortgage operations."
6. End with a warm, professional closing (default: "Cheers, {my_name}").  
   Alternative closings like "Best," or "Regards," are fine but must include your name: {my_name}.
7. Avoid these words entirely: exploring, interested, learning, no easy feat, impressive, noteworthy, remarkable, fascinating, admiring, inspiring, no small feat, no easy task, stood out.



Example format (keep this exact structure):
Hi Michael,
Glad to be connected. Your work in both banking and public infrastructure is shaping meaningful momentum in McKinney. Would love to exchange thoughts on how local lending teams are streamlining workflows—open to a quick chat sometime?
Cheers, Joseph

Now create for:
Prospect: {state['prospect_name']} ({state['designation']} at {state['company']})
Industry: {state['industry']}
Key Highlight: {state['prospect_background']}

Message (MAX 2-3 LINES within 250 chars - follow the pattern above):
Hi {prospect_first_name},"""

    
    

    try:
        response = groq_llm(prompt, temperature=0.7)
        # Clean response
        message = response.strip()
        unwanted_starts = [
            "Here is a LinkedIn connection message",
            "Here’s a LinkedIn message",
            "LinkedIn connection message:",
            "Message:",
            "Output:"
        ]
        for phrase in unwanted_starts:
            if message.lower().startswith(phrase.lower()):
                message = message.split("\n", 1)[-1].strip()

        # Ensure connection note is present
        # connection_phrases = ["look forward", "would be great", "hope to connect", "love to connect", "looking forward"]
        # if not any(phrase in message.lower() for phrase in connection_phrases):
        #     # Add connection note if missing
        #     message += "\nI'll be there too & looking forward to catching up with you at the event."
            
        # if message.count(f"Best, {my_name}") > 1:
        #     parts = message.split(f"Best, {my_name}")
        #     message = parts[0].strip() + f"\n\nBest, {my_name}"
        if "Glad to be connected" not in message:
            lines = message.split("\n")
            if len(lines) > 1:
                lines.insert(1, "Glad to be connected.")
            else:
                message = f"{lines[0]}\nGlad to be connected."
            message = "\n".join(lines)

# Strip forbidden flattery words if the model sneaks them in
        for word in ["exploring", "interested", "learning", "impressive", "noteworthy", "remarkable", 
             "fascinating", "admiring", "inspiring", "no small feat", "no easy task", "stood out"]:
            message = re.sub(rf"\b{word}\b", "", message, flags=re.IGNORECASE).strip()


        return {**state, "final_message": message}
    except Exception as e:
        print(f"Message generation failed: {e}")
        return {**state, "final_message": "Failed to generate message"}
# =====================
# Build LangGraph Workflow
# =====================
workflow = StateGraph(ProspectMessageState)
workflow.add_node("summarize_backgrounds", summarize_backgrounds)
workflow.add_node("generate_message", generate_message)
workflow.set_entry_point("summarize_backgrounds")
workflow.add_edge("summarize_backgrounds", "generate_message")
workflow.add_edge("generate_message", END)
graph1 = workflow.compile()

# =====================
# Streamlit UI
# =====================
st.set_page_config(page_title="LinkedIn Message Generator", layout="centered")
st.title("Msgs for Speridian")

with st.form("prospect_form"):
    prospect_name = st.text_input("Prospect Name", "")
    designation =""
    company = ""
    industry =""
    prospect_background = st.text_area("Prospect Background", "Prospect professional background goes here...")

    submitted = st.form_submit_button("Generate Message")

if submitted:
    with st.spinner("Generating message..."):
        initial_state: ProspectMessageState = {
            "prospect_name": prospect_name,
            "designation": designation,
            "company": company,
            "industry": industry,
            "prospect_background": prospect_background,

        }
        result = graph1.invoke(initial_state)

    st.success(" Message Generated!")
    st.text_area("Final LinkedIn Message", result["final_message"], height=200, key="final_msg")

    # Copy button using JavaScript
    copy_code = f"""
    <script>
    function copyToClipboard() {{
        var text = `{result['final_message']}`;
        navigator.clipboard.writeText(text).then(() => {{
            alert("Message copied to clipboard!");
        }});
    }}
    </script>
    <button onclick="copyToClipboard()"> Copy Message</button>
    """

    st.components.v1.html(copy_code, height=50)

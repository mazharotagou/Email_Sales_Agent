
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import os
from agents import Agent, trace, Runner, AsyncOpenAI, OpenAIChatCompletionsModel, function_tool
import smtplib
from email.message import EmailMessage
from pydantic import EmailStr, BaseModel
import asyncio
import json
import re






#loading environmental variables
load_dotenv()
gmail_user = os.getenv("GMAIL_USERNAME")
gmail_password = os.getenv("GMAIL_PASSWORD")
os.environ["OPENAI_API_KEY"]  = os.getenv("OPENAI_API_KEY")

groq_baseurl = "https://api.groq.com/openai/v1"
deepseek_baseurl = "https://api.deepseek.com"

groq_client = AsyncOpenAI(api_key = os.getenv("GROQ_API_KEY"), base_url = groq_baseurl)
deepseek_client = AsyncOpenAI(api_key = os.getenv("DEEPSEEK_API_KEY"), base_url = deepseek_baseurl)

groq_model = OpenAIChatCompletionsModel(model = "llama-3.3-70b-versatile", openai_client = groq_client)
deepseek_model = OpenAIChatCompletionsModel(model = "deepseek-chat", openai_client = deepseek_client)

#----------------------------------------------------------------



def text_extraction(file):
    reader = PdfReader(file)
    content = ""
    for page in reader.pages:
        content += page.extract_text() + "\n\n"
    return content

GCP_documentation = text_extraction("docs/GCPdocument.pdf")
ethics_documentation = text_extraction("docs/ethicsdocument.pdf")

#Tools for agents use
@function_tool
def send_email(subject : str = None, body : str = None, recipient : EmailStr = None ):
    """This tool is used for only sending the email to the recipient"""
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = gmail_user
    msg['To'] = recipient
    msg.set_content(body)

    # Send Email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(gmail_user, gmail_password)
        response = smtp.send_message(msg)
        if response == {}:
            return {"role":"tool","email_status":"successful"}
        else:
            return {"role":"tool","email_status":"failed"}

#print (send_email(subject = "whats up?", body = "I am good", recipient = "mazharotagou@gmail.com"))

orchestrator_instructions = f"""
    You are an orchestrator agent.
    You will receive the message from the user and decide:

    1. If it is related to {GCP_documentation}, select "GCP_agent"
    2. If it is related to {ethics_documentation}, select "ethics_agent"
    3. If it is related to neither, select "none"

    Return valid JSON only in this format:
    {{
    "selected_agent": "GCP_agent | ethics_agent | none",
    "reasoning": "why you chose it",
    "confidence": 0.0
    }}
    """

gcp_agent_instructions = f"""You will receive a message from the user. Using your best judgment and the knowledge provided in the following documentation:
    {GCP_documentation}

    Your task is to draft the body of an email response that is:
    - begin with Dear [name of the requester]
    - end with [Kind regards, \n Innovation Manager]
    - accurate
    - brief
    - professional
    - clear
    - concise
    - directly relevant to the user's message
    - Don't format any text

    Base your response on the provided GCP documentation. Do not invent facts. Where the documentation is unclear or insufficient, remain cautious and avoid making unsupported claims.

    Write only the email body, not the subject line or any extra commentary.

    Produce output only in the form of json, strictly in the following format:
    {{"email_recipient": EmailStr,
    "body":str}}
    """

ethics_agent_instructions = f"""You will receive a message from the user. Using your best judgment and the knowledge provided in the following documentation:
    {ethics_documentation}

    Your task is to draft the body of an email response that is:
    - begin with Dear [name of the requester]
    - end with [Kind regards, \n Innovation Manager]
    - accurate
    - brief
    - professional
    - clear
    - concise
    - directly relevant to the user's message
    - don't format any text

    Base your response on the provided GCP documentation. Do not invent facts. Where the documentation is unclear or insufficient, remain cautious and avoid making unsupported claims.

    Write only the email body, not the subject line or any extra commentary.

    Produce output only in the form of json, strictly in the following format:
    {{"email_recipient": EmailStr,
    "body":str}}
    """

editing_instructions = f"""
    You are an Email Editing Orchestrator Agent.

    Your job is to process an email.

    Follow these steps STRICTLY:

    STEP 1: Generate Subject
    - Call the `subject_writer_tool`
    - Pass the FULL email body as input
    - Store the returned subject

    STEP 2: Format Email Body
    - Call the `body_formatting_tool`
    - Pass the FULL email body as input
    - Store the returned HTML body


    CRITICAL RULES:
    - You MUST use BOTH tools
    - You MUST call subject_writer_tool FIRST
    - You MUST call body_formatting_tool SECOND
    - You MUST NOT generate subject or HTML yourself
    - You MUST NOT skip any step

    OUTPUT RULES:
    - Do NOT return text to the user
    - ONLY use tools

    Your role is orchestration, NOT content creation.

    Generate OUTPUT as a JSON object with following format: {{
        'subject': str, 'body': str, 'recipient': EmailStr
    }}
    """

subject_writer_instructions = """
    You are a Subject Line Generator.

    Your ONLY task:
    - Generate a clear, professional, and concise email subject line.

    Rules:
    - Output ONLY the subject line (plain text).
    - Do NOT include quotes.
    - Do NOT include explanations.
    - Do NOT format as HTML.
    - Keep it under 10 words if possible.
    - Ensure it reflects the intent of the email.

    You are NOT allowed to edit or rewrite the email body.
    """
body_formatting_instrucitons = """
    You are an Email HTML Formatter.

    Your ONLY task:
    - Convert a plain text email into clean HTML compatible with Microsoft Outlook and other email clients.

    Formatting rules:
    - Use ONLY simple HTML:
        <p>, <br>, <strong>, <em>
    - Do NOT use:
        <div>, <style>, CSS, JavaScript

    Enhancement rules:
    - Improve readability and structure
    - Add paragraph breaks where needed
    - Emphasize key points using:
        <strong> for important information
        <em> for subtle emphasis
    - Do NOT overuse formatting

    Output rules:
    - Return ONLY valid HTML, with EMAIL Body
    - No explanations
    - No markdown
    """

subject_writer_agent = Agent(name = "subject_writer_agent", model = deepseek_model, instructions = subject_writer_instructions)
body_formatting_agent = Agent(name="body_formatting_agent", model = deepseek_model, instructions = body_formatting_instrucitons)

subject_writer_tool_description = """
    Use this tool ONLY to generate the subject line for an email.

    Input: full email body
    Output: a short subject line (plain text)

    Do NOT use this tool for editing or formatting the email body.
    """
body_formatter_tool_description = """
    Use this tool ONLY to convert a plain email body into HTML.

    Input: plain text email body
    Output: HTML formatted email body (Outlook-compatible)

    Do NOT use this tool to generate subject lines.
    """

subject_writer_tool = subject_writer_agent.as_tool(tool_name = "subject_writer_tool", tool_description = subject_writer_tool_description)
body_formatter_tool =body_formatting_agent.as_tool(tool_name = "body_formatting_tool", tool_description = body_formatter_tool_description)

editing_tools = [subject_writer_tool, body_formatter_tool]

editing_agent = Agent(name="Editing_agent", model = deepseek_model, instructions = editing_instructions, tools = editing_tools)

#handoffs = [editing_agent]
orchestrator = Agent(name = "Orchestrator", model = deepseek_model, instructions=orchestrator_instructions)
gcp_agent = Agent(name = "GCP_agent", model = deepseek_model, instructions = gcp_agent_instructions)
ethics_agent = Agent(name = "Ethics_agent", model = deepseek_model, instructions = ethics_agent_instructions)

recipient_email = "mazharotagou@gmail.com"

message = f"""Dear Manager,
I am looking to conduct a clinical trial on human patients. The trial is related to recently invented drug against cerebral palsy.
Could you please provide me resources so that I can produce my work plan?
I look forward to hearing from you.

Kind regards,
Mazhar
"""

new_message = f"""Recipient email: {recipient_email}

Email/body request:
{message}
"""
async def orchestrator_function():
    response = await Runner.run(orchestrator, new_message)
    response = response.final_output
    response = re.sub(r"```json|```", "", response).strip()
    response = json.loads(response)
    return response

async def gcp_agent_function():
    response = await Runner.run(gcp_agent, new_message)
    response = response.final_output
    response = re.sub(r"```json|```", "", response).strip()
    response = json.loads(response)
    print (response)
    return response

async def ethics_agent_function():
    response = await Runner.run(ethics_agent, new_message)
    response = response.final_output
    response = re.sub(r"```json|```", "", response).strip()
    response = json.loads(response)
    print (response)
    return response

async def editing_agent_function(agent_response):
    agent_response = f""" email_recipient : {agent_response['email_recipient']},
                        email_body : {agent_response['body']} """
    response = await Runner.run(editing_agent, agent_response)
    response = response.final_output
    #response = re.sub(r"```json|```", "", response).strip()
    #response = json.loads(response)
    print (response)
    return response

async def main():
    with trace("Mazhar checks"):
        response = await orchestrator_function()
        print (response)
        if response["selected_agent"] == "GCP_agent":
            print ("GCP_Agent_Activated")
            agent_response = await gcp_agent_function()
            
        elif response["selected_agent"] == "ethics_agent":
            print ("Ethics_Agent_Activated")
            agent_response = await ethics_agent_function()

        editor_response = await editing_agent_function(agent_response)
        print ("Editor Response     :",  editor_response)

        
        

asyncio.run(main())


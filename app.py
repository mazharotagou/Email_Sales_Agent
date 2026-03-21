from ast import arguments
import requests
import os
import sendgrid
import smtplib
from email.message import EmailMessage
from sendgrid.helpers.mail import Mail, Email, To, Content
from dotenv import load_dotenv
from pydantic import EmailStr
from openai import OpenAI, base_url
from agents import Agent, function_tool, trace, Runner, AsyncOpenAI, OpenAIChatCompletionsModel
import asyncio
from PyPDF2 import PdfReader


def text_extraction(file):
    reader = PdfReader(file)
    content = ""
    for page in reader.pages:
        content += page.extract_text() + "\n\n"

    
    return content

GCP_documentation = text_extraction("docs/GCPdocument.pdf")
ethics_documentation = text_extraction("docs/ethicsdocument.pdf")


load_dotenv()


gmail_user = os.getenv("GMAIL_USERNAME")
gmail_password = os.getenv("GMAIL_PASSWORD")

email_address_for_info = "mazharotagou@gmail.com"

openai_api_key = os.getenv("OPENAI_API_KEY")
print(str(openai_api_key))
os.environ["OPENAI_API_KEY"]  = openai_api_key

print(openai_api_key)


groq_baseurl = "https://api.groq.com/openai/v1"
deepseek_baseurl = "https://api.deepseek.com"

groq_client = AsyncOpenAI(api_key = os.getenv("GROQ_API_KEY"), base_url = groq_baseurl)
deepseek_client = AsyncOpenAI(api_key = os.getenv("DEEPSEEK_API_KEY"), base_url = deepseek_baseurl)

groq_model = OpenAIChatCompletionsModel(model = "llama-3.3-70b-versatile", openai_client = groq_client)
deepseek_model = OpenAIChatCompletionsModel(model = "deepseek-chat", openai_client = deepseek_client)


@function_tool
def send_email(subject : str = None, body : str = None, recipient : EmailStr = None ):
    """This tool is used for sending the email to the recipient"""
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = gmail_user
    msg['To'] = recipient
    msg.set_content(body)

    # Send Email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(gmail_user, gmail_password)
        smtp.send_message(msg)


#inputs = {'subject' : 'this is a check email', 'body' : 'this should mark the body of the email', 'recipient' : 'mazharotagou@gmail.com'}
#send_email(**inputs)
"""
manager_instructions = f"You are an innovation manager. You are incharge of manager of the ethics and good clinical practices units. \
    You will check new emails coming using check_email tool. Then, you will determine, if the email is relevant to ethics and/or good clinical practices. \
        Proceed only with the Emails that are relevant to you (Ethics and/or Good clinical practices). \
            Then, handover the email to relevant agent ethics_agent and/or gcp_agent. If possible, inform the sender of the email that their email has been recieved and has been allocated to relevant department (Ethics Unit and/or Good Clinical Practices Unit)."

"""
manager_instructions = f"You are an Innovation Manager, who heads the ethics and good clinical practices departments. Based on the requests, you either handoff task with instructions to ethics_officer or gcp_officer. \
    Based on the request, the task can also be given to both if the request is based on both domains. You work as an orchestrator. \
    Your job is to be discreet. Once you alocate the task, you inform using send_email tool to {email_address_for_info}. The email has been recieved and has been aloted to either Ethics Officer or/and Good Clinical Practices Officer."

ethics_officer_instructions = f"You are an Ethics Officer and you are subject matter expert. Your task is to answer users queries in the form of an email body, that is concise, brief, and to-the-point. \
    Your name is Alexa Benzene. You will write email body addressing the name of the person in the email if the name is known else you will use Australian convention.\
        In order to craft answers, you will take instructions from innovation_manager and will use your knowledge on the domain provided below: {ethics_documentation}. \
            You will be professional, polite, and concise in your response. \
                You will make sure that people's privacy is secure, while communicating."

gcp_officer_instructions = f"You are a good clinical practices Officer (GCP) and you are a subject matter expert. Your task is to answer users queries in the form of an email body, that is concise, brief and to the point. \
    Your name is Siri Adamantane. You will write email body addressing the name of the person in the email if the name is known else you will use Australian convention. \
        In order to craft answers, you will be strictly using the information provided in the subsequent document: {GCP_documentation}. \
            You will be professional, polite, and concise in your response. You will be accurate in responding and will respectfully decline to answer if you are not sure. \
            You will make sure that people's privacy is secure, while communicating."



subject_writer_instructions = f"Your job is to read the body of the email provided and you analyse the text. Then, you provide the most appropriate subject of the email."
formatting_instructions = f"Your job is to read the email body and then format it so that the emphasis is placed on salient lines or words or phrases (bold/italics text)."

email_subject_writer = Agent(name = "email_subject_writer", model = deepseek_model, instructions = subject_writer_instructions)
email_formatter = Agent(name = "email_formatter", model = deepseek_model, instructions = formatting_instructions)

email_subject_writer_tool = email_subject_writer.as_tool(tool_name="subject_writer_tool", tool_description = "This tool is used to write appropriate subject line of the email")
email_formatter_tool = email_formatter.as_tool(tool_name = "email_formatter_tool", tool_description= "This tool is used to do formatting of the email body")

tools_email_review = [email_subject_writer_tool, email_formatter_tool, send_email]

email_reviewing_officer_instructions = f"You are an email reviewing officer, and you are going to work on one email at a time. You will either recieve email from ethics_officer or gcp_officer. You will not combine emails together. \
    You will use email_subject_writer_tool to come up with the approproate subject line of the email. You will use email_formatter_tool to do html formatting so that emphasize is placed on write place by using bold and/or italics lines/phrases/words. \
        Then, you use send_email tool to send email to {email_address_for_info}."

email_reviewing_officer = Agent(name = "email_reviewing_agent", handoff_description = "writes the subject line for the email, and perform formatting of the email, and then send email", instructions = email_reviewing_officer_instructions, tools = tools_email_review, model = deepseek_model)

operational_officer_handoffs = [email_reviewing_officer]

ethics_officer = Agent(name = "Alexa_Benzene", model = deepseek_model, handoff_description = "Writes email body related to ethics related matters", instructions = ethics_officer_instructions, handoffs = operational_officer_handoffs)
gcp_officer = Agent(name = "Siri_Adamantane", model = deepseek_model, handoff_description = "Writes email body related to Good clinical practices related matters", instructions = gcp_officer_instructions, handoffs = operational_officer_handoffs)

innovation_manager_tools = [send_email]
innovation_manager_handoffs = [ethics_officer , gcp_officer]
innovation_manager = Agent(name = "Innovation_Manager", instructions = manager_instructions, model = deepseek_model, tools = innovation_manager_tools, handoffs = innovation_manager_handoffs)

message = f"Dear Innovation Manager, \
    I am writing to obtain some guidance on an issue related to mouse handling for my experiments. I was wondering if you could guide me to the methods, which can be used for Euthanising the animal. \
        It will be very helpful. I look forward to hearing from you. Kind regards. Please send me email at mazharotagou@gmail.com. \
        Mazhar"

async def main():
    with trace("Mazhar's running"):
        result = await Runner.run(innovation_manager, message)
        print (result)

asyncio.run(main())
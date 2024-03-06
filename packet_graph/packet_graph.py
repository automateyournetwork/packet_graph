import os
import json
import subprocess
import streamlit as st
import networkx as nx
from pyvis.network import Network
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.graphs.networkx_graph import KG_TRIPLE_DELIMITER
from langchain.prompts import PromptTemplate
import streamlit.components.v1 as components

# Load environment variables
load_dotenv()
openai_api_key = os.getenv('OPENAI_API_KEY')

# Prompt template for knowledge triple extraction
_DEFAULT_KNOWLEDGE_TRIPLE_EXTRACTION_TEMPLATE = (
    "You are a networked intelligence helping a human track knowledge triples"
    " about all relevant people, things, concepts, etc. and integrating"
    " them with your knowledge stored within your weights"
    " as well as that stored in a knowledge graph."
    " Extract all of the knowledge triples from the text."
    " A knowledge triple is a clause that contains a subject, a predicate,"
    " and an object. The subject is the entity being described,"
    " the predicate is the property of the subject that is being"
    " described, and the object is the value of the property.\n\n"
    "EXAMPLE\n"
    "It's a state in the US. It's also the number 1 producer of gold in the US.\n\n"
    f"Output: (Nevada, is a, state){KG_TRIPLE_DELIMITER}(Nevada, is in, US)"
    f"{KG_TRIPLE_DELIMITER}(Nevada, is the number 1 producer of, gold)\n"
    "END OF EXAMPLE\n\n"
    "EXAMPLE\n"
    "I'm going to the store.\n\n"
    "Output: NONE\n"
    "END OF EXAMPLE\n\n"
    "EXAMPLE\n"
    "Oh huh. I know Descartes likes to drive antique scooters and play the mandolin.\n"
    f"Output: (Descartes, likes to drive, antique scooters){KG_TRIPLE_DELIMITER}(Descartes, plays, mandolin)\n"
    "END OF EXAMPLE\n\n"
    "EXAMPLE\n"
    "{text}"
    "Output:"
)

KNOWLEDGE_TRIPLE_EXTRACTION_PROMPT = PromptTemplate(
    input_variables=["text"],
    template=_DEFAULT_KNOWLEDGE_TRIPLE_EXTRACTION_TEMPLATE,
)

llm = ChatOpenAI(temperature=0.9, model="gpt-4-1106-preview")

# Create an LLMChain using the knowledge triple extraction prompt
chain = LLMChain(llm=llm, prompt=KNOWLEDGE_TRIPLE_EXTRACTION_PROMPT)


class GraphPCAP:
    def __init__(self, json_path):
        self.json_path = json_path
        self.triples_list = []

    def load_json_and_extract_text(self):
        with open(self.json_path, 'r') as file:
            data = json.load(file)
        # Join all formatted data into a single text string
        text = json.dumps(data)

        return text
    
    def generate_knowledge_graph(self):
        text = self.load_json_and_extract_text()
        triples = chain.invoke({'text': text}).get('text')
        self.triples_list = self.parse_triples(triples)

    def parse_triples(self, response, delimiter=KG_TRIPLE_DELIMITER):
        if not response:
            return []
        return [triple.strip() for triple in response.split(delimiter) if triple.strip()]

    def create_graph_from_triplets(self):
        G = nx.DiGraph()
        for triplet in self.triples_list:
            # Safely parse triples ensuring there are exactly three parts
            parts = triplet.split(',')
            if len(parts) == 3:
                subject, predicate, obj = parts
                G.add_edge(subject.strip(), obj.strip(), label=predicate.strip())
            else:
                print(f"Invalid triplet skipped: {triplet}")
        return G

    def nx_to_pyvis(self, networkx_graph):
        pyvis_graph = Network(height="600px", width="100%", bgcolor="#222222", font_color="white")
        pyvis_graph.from_nx(networkx_graph)
        pyvis_graph.save_graph("graph.html")
        # Read the HTML content from the file
        with open("graph.html", "r") as file:
            html_content = file.read()

        # Use Streamlit components to embed the HTML content
        components.html(html_content, width=700, height=600, scrolling=True)        

# Function to convert pcap to JSON
def pcap_to_json(pcap_path, json_path):
    command = f'tshark -nlr {pcap_path} -T json > {json_path}'
    subprocess.run(command, shell=True)

# Streamlit UI for uploading and converting pcap file
def upload_and_convert_pcap():
    st.title('Packet Graph - Graph Packet Captures')
    uploaded_file = st.file_uploader("Choose a PCAP file", type="pcap")
    if uploaded_file:
        if not os.path.exists('temp'):
            os.makedirs('temp')
        pcap_path = os.path.join("temp", uploaded_file.name)
        json_path = pcap_path + ".json"
        with open(pcap_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        pcap_to_json(pcap_path, json_path)
        st.session_state['json_path'] = json_path
        st.success("PCAP file uploaded and converted to JSON.")
        if st.button("Proceed to Graph"):
            st.session_state['page'] = 2
            graph_pcap()

def graph_pcap():
    st.title('Knowledge Graph from Packet Capture')
    json_path = st.session_state.get('json_path')
    if json_path:
        graph_pcap_instance = GraphPCAP(json_path)
        graph_pcap_instance.generate_knowledge_graph()
        graph = graph_pcap_instance.create_graph_from_triplets()
        graph_pcap_instance.nx_to_pyvis(graph)
        HtmlFile = open("graph.html", 'r', encoding='utf-8')
        source_code = HtmlFile.read() 
        components.html(source_code, height=600, width=800)

if __name__ == "__main__":
    if 'page' not in st.session_state:
        st.session_state['page'] = 1

    if st.session_state['page'] == 1:
        upload_and_convert_pcap()
    elif st.session_state['page'] == 2:
        graph_pcap()
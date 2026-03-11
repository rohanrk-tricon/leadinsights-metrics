from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_ollama import ChatOllama


class QueryAgent:

    def __init__(self, dataframe):

        self.df = dataframe

        self.llm = ChatOllama(
            model="llama3",
            temperature=0,
            base_url="http://localhost:11435"
        )

        self.agent = create_pandas_dataframe_agent(
                    llm=self.llm,
                    df=self.df,
                    verbose=True,
                    allow_dangerous_code=True
                )

        # max_iterations=1 # force agent to answer in one step

    def ask(self, question: str):

        response = self.agent.invoke(question)

        return response["output"]
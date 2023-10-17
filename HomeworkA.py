import time
import pandas as pd
from langchain.llms import AzureOpenAI
import json
import streamlit as st
from langchain.agents import create_pandas_dataframe_agent

llm = AzureOpenAI(openai_api_base="https://oh-ai-openai-scu.openai.azure.com/",
                  openai_api_key="617447e973f0448fa9342c8c807bb496",
                  deployment_name="gpt-35-turbo",
                  model="gpt-35-turbo",
                  openai_api_type="azure",
                  openai_api_version="2023-05-15", temperature=0)


# 告诉llm对于画图输出的格式进行规范，文本及其兜底，如果最终输出是和输入完全不同的表也可以
def queryAdjustFinal(agent, query):
    prompt = (
            """
                For the following query, if it requires drawing a table, reply as follows:
                {"table": {"columns": ["column1", "column2", ...], "data": [[value1, value2, ...], [value1, value2, ...], ...]}}

                If the query requires creating a bar chart, reply as follows:
                {"bar": {"columns": ["A", "B", "C", ...], "data": [25, 24, 10, ...]}}

                If the query requires creating a line chart, reply as follows:
                {"line": {"columns": ["A", "B", "C", ...], "data": [25, 24, 10, ...]}}

                If the query requires creating a scatter chart, reply as follows:
                {"scatter": {"columns": ["column1", "column2", ...], "data": [25, 24, ...], [34, 52, ...], ...}}

                There can only be three types of chart, "scatter", "bar" and "line".

                If it is just asking a question that requires neither, reply as follows:
                {"answer": "answer"}
                Example:
                {"answer": "The title with the highest rating is 'Gilead'"}

                If you do not know the answer, reply as follows:
                {"answer": "I do not know."}

                Return all output as a string.

                All strings in "columns" list and data list, should be in double quotes,

                For example: {"columns": ["title", "ratings_count"], "data": [["Gilead", 361], ["Spider's Web", 5164]]}

                Lets think step by step.

                Below is the query.
                Query: 
                """
            + query
    )
    response = agent.run(prompt).__str__()
    return response[:response.rfind("}") + 1]


# 对返回的图进行解析画图，还有文本答案直接输出，对于表进行解析
def writeResponse(ans: dict):
    # 检查返回是否是文本.
    if "answer" in ans:
        st.write(ans["answer"])
    # 检查返回是不是bar chart.
    if "bar" in ans:
        data = ans["bar"]
        try:
            df1 = pd.DataFrame(data)
            df1.set_index("columns", inplace=True)
            st.bar_chart(df1)
        except:
            st.write("draw chart failed, please try again")
    # 检查返回是不是line chart.
    if "line" in ans:
        data = ans["line"]
        try:
            df1 = pd.DataFrame(data)
            df1.set_index("columns", inplace=True)
            st.line_chart(df1)
        except:
            st.write("draw chart failed, please try again")
    # 检查返回是不是scatter chart.
    if "scatter" in ans:
        data = ans["scatter"]
        try:
            df1 = pd.DataFrame(data["data"], columns=data["columns"])
            st.scatter_chart(df1)
        except:
            st.write("draw chart failed, please try again")
    # 检查返回是不是table.
    if "table" in ans:
        data = ans["table"]
        df1 = pd.DataFrame(data["data"], columns=data["columns"])
        st.table(df1)


# 对返回的python代码掐头去尾
def removeHeader(variable):
    return "``" not in variable and "im_end" not in variable


st.title("Homework A")
st.write("""支持特殊输出和样例：（鉴于langchain agent输出长度有限制只能输出很小的图）\n
可以直接问问题会有文本答案\n
表：需要关键字"I want to reuse result."。可以使用上次表结果作为下次输入（表只显示前五行但是全部表都是在的）\n
对于这个表可以转存需要关键字“I want to save last table as:”\n
柱状图：需要关键字bar chart. \n
线图：需要关键字line chart. \n
散点图：需要关键字scatter chart. """)
st.write("Please upload your Excel file below.")
data = st.file_uploader("Upload a Excel")
while (data is None):
    time.sleep(1)
query = st.text_area("Insert your query",key="0")
while (query is None):
    time.sleep(1)
try:
    df = pd.read_excel(data, engine='openpyxl')
except:
    st.write("fail to read file")
flag = True
key = 1
while (flag):
    # 对输入表进行加工且保留结果给下个query作为输入
    if "I want to reuse result." in query:
        # 告诉llm要输出python代码
        prompt = ("give me the python code of: " + query.replace("I want to reuse result.", ""))
        agent = create_pandas_dataframe_agent(llm, df, handle_parsing_errors=True, verbose=True, max_iterations=25)
        ansx = agent.run(prompt)
        # 对输出掐头去尾，有多句就进行分割
        st.write("code generated:  " + ansx)
        codeList = ansx.__str__().replace("<|im_end|>", "").split("\n")
        if (len(codeList) > 1):
            codeList = list(filter(removeHeader, codeList))
        try:
            # 逐行执行分割完的代码
            for code in codeList:
                dfx = exec(code)
        except:
            # 执行失败就返回1
            dfx = "1"
        # 如果返回的代码直接改变了df就用df展示，且用df迭代
        if dfx is None:
            #agent = create_pandas_dataframe_agent(llm, df, handle_parsing_errors=True, verbose=True)
            st.table(df.head(5))
            query = st.text_area("Insert your new query", key=key.__str__())
        # 不然就用dfx迭代
        else:
            if isinstance(dfx, pd.DataFrame):
                df = dfx
                #agent = create_pandas_dataframe_agent(llm, dfx, handle_parsing_errors=True, verbose=True)
                st.table(df.head(5))
                query = st.text_area("Insert your new query", key=key.__str__())
            else:
                # 执行失败或者返回不是dataframe就走兜底
                query = st.text_area("I can not understand you, Insert another query", key=key.__str__())

    else:
        flag = False
        # 用户要求保存就保存
        if "I want to save last table as:" in query:
            try:
                file=query.replace("I want to save last table as:","").strip()+".xlsx"
                df.to_excel(file)
                st.write("table saved as " + file)
            except:
                st.write("table saved failed")
        # 以上都不是就判断是不是走画图或者文本问题或者特殊表
        else:
            try:
                agent = create_pandas_dataframe_agent(llm, df, handle_parsing_errors=True, verbose=True,max_iterations=25)
                ansRaw = queryAdjustFinal(agent, query).replace("\'", "\"")
                st.write("Raw answer: \"" + ansRaw + "\"")
            except:
                st.write("Agent error")
            try:
                ans = json.loads(ansRaw)
                writeResponse(ans)
            except:
                st.write("Decode json failed, please try again")
    key = key + 1


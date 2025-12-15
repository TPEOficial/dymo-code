import os, json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY")
)

messages = [
    {
        "role": "system",
        "content": "You are a helpful agent; you are very concise with your answers."
    }
]

def list_files_in_dir(directory="."):
    try: return os.listdir(directory)
    except: return []

def read_file(file_path):
    try: return open(file_path, "r").read()
    except: return ""

def create_folder(folder_path):
    try: return os.mkdir(folder_path)
    except: return ""

def create_file(file_path, content):
    try: return open(file_path, "w").write(content)
    except: return ""

tools = [
    {
      "type": "function",
      "function": {
        "name": "list_files_in_dir",
        "description": "List all files in a directory",
        "parameters": {
          "type": "object",
          "properties": {
            "directory": {
              "type": "string",
              "description": "The directory to list files in (Default: current directory)"
            }
          },
          # "required": [""]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "read_file",
        "description": "Read a file",
        "parameters": {
          "type": "object",
          "properties": {
            "file_path": {
              "type": "string",
              "description": "The path to the file to read"
            }
          },
          "required": ["file_path"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "create_folder",
        "description": "Create a folder",
        "parameters": {
          "type": "object",
          "properties": {
            "folder_path": {
              "type": "string",
              "description": "The path to the folder to create"
            }
          },
          "required": ["folder_path"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "create_file",
        "description": "Create a file",
        "parameters": {
          "type": "object",
          "properties": {
            "file_path": {
              "type": "string",
              "description": "The path to the file to create"
            },
            "content": {
              "type": "string",
              "description": "The content to write to the file"
            }
          },
          "required": ["file_path", "content"]
        }
      }
    }
]

while True:

    user_input = input("You: ").strip()

    if not user_input: continue

    if user_input.lower() == "exit": break

    messages.append(
        {
            "role": "user",
            "content": user_input
        }
    )

    response_text = ""

    stream = client.chat.completions.create(
        messages=messages,
        model="llama-3.3-70b-versatile",
        tools=tools,
        stream=True
    )

    fn_call = None

    for chunk in stream:
        choice = chunk.choices[0]
        delta = choice.delta

        if delta.tool_calls:
            fn_call = delta.tool_calls[0].function
            continue

        if delta.content:
            print(f"{delta.content}", end="")
            response_text += delta.content

    print()

    if fn_call:
        args = {}
        if fn_call.arguments:
            try:
                args = json.loads(fn_call.arguments)
            except json.JSONDecodeError as e:
                print(f"Error parsing function arguments: {fn_call.arguments}")
                print(f"JSONDecodeError: {e}")
        
        if fn_call.name == "list_files_in_dir": result = list_files_in_dir(**args)
        elif fn_call.name == "read_file": result = read_file(**args)
        elif fn_call.name == "create_folder": result = create_folder(**args)
        elif fn_call.name == "create_file": result = create_file(**args)
        else: result = f"Function {fn_call.name} not implemented."

        messages.append(
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": fn_call.name,
                            "arguments": json.dumps(args)
                        }
                    }
                ]
            }
        )

        messages.append(
            {
                "role": "tool",
                "tool_call_id": "tool-call-1",
                "content": f"{result}"
            }
        )

        follow_up = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile"
        )

        print(follow_up.choices[0].message.content)
        messages.append({"role": "assistant", "content": follow_up.choices[0].message.content})

    else: messages.append({"role": "assistant", "content": response_text})
EMBODIED_SYSTEM_PROMPT="You are a robot in given room. You need to complete the tasks according to human instructions. We provide an Available_Actions set and the corresponding explanations for each action. Each step, you should select one action from Available_Actions."

TASK_PREFIX_PUT="""This is an image from your frontal perspective. Please select an action from the Available_Actions and fill in the arguments.
Task: "{task_name}"
Available_Actions: {{
"navigate to <object>": Move to the object.
"pickup <object>": Pick up the object.
"put <object>": Put the item in your hand into or on the object.
"toggle <object>": Switch the object on or off.
"open <object>": Open the object (container), and you will see inside the object.
"close <object>": Close the object.
"observe": You can obtain image of your directly rear, left, and right perspectives.
"move forward": Move forward to see more clearly.
"end": If you think you have completed the task, please output "end".}}
Before making each decision, you can think, plan, and even reflect step by step, and then output your final action.
Your final action must strictly follow format: <DecisionMaking>Your Action</DecisionMaking>, for example, <DecisionMaking>observe</DecisionMaking>."""

# for MODE=API put in
TASK_PREFIX_PUT_IN="""This is an image from your frontal perspective. Please select an action from the Available_Actions and fill in the arguments.
Task: "{task_name}"
Available_Actions: {{
"navigate to <object>": Move to the object.
"pickup <object>": Pick up the object.
"put in <object>": Put the item in your hand into or on the object.
"toggle <object>": Switch the object on or off.
"open <object>": Open the object (container), and you will see inside the object.
"close <object>": Close the object.
"observe": You can obtain image of your directly rear, left, and right perspectives.
"move forward": Move forward to see more clearly.
"end": If you think you have completed the task, please output "end".}}
Before making each decision, you can think, plan, and even reflect step by step, and then output your final action.
Your final action must strictly follow format: <DecisionMaking>Your Action</DecisionMaking>, for example, <DecisionMaking>observe</DecisionMaking>."""



USER_IMAGE_PREFIX="""After executing your previous "{action}", you get this new image above.
To complete your task, you can think step by step at first and then output your new action from the Available_Actions.
Your action must strictly follow format: <DecisionMaking>Your Action</DecisionMaking>, for example, <DecisionMaking>observe</DecisionMaking>."""

USER_IMAGE_PREFIX_ERROR="""To complete your task, you can think step by step at first and then output your new action from the Available_Actions.
Your action must strictly follow format: <DecisionMaking>Your Action</DecisionMaking>, for example, <DecisionMaking>observe</DecisionMaking>."""

USER_IMAGE_PREFIX_MOVE_FORWARD="""After executing your previous "{action}", you get this new image above.
You can use "navigate to <object>" to reach nearby, larger objects for closer inspection.
To complete your task, you can think step by step at first and then output your new action from the Available_Actions.
Your action must strictly follow format: <DecisionMaking>Your Action</DecisionMaking>, for example, <DecisionMaking>observe</DecisionMaking>."""



MATCH_PROMPT="""Please select the object from the candidate list that most closely matches the description provided.
Candidate Object List: {objects}.
Description: {description}.
You must select one object from the Candidate Object List. Do not choose objects outside of the Candidate Object List.
Make sure to only output the selected object and avoid including anything else in your response.
"""

INVALID_ACTION_PROMPT="""Action is illegal. Please select an action from the Available_Actions."""

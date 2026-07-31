from django import template
import json
import ast
register = template.Library()

@register.filter

def loadjson(data):
    json_data = {}
    # json_data = json.loads(data)
    json_data= json.loads(data)
    print(json_data)
    # for i in json_data:
    #     value = json_data[i]
    #     print(i, value)
    #
    # json_data['invoice_number']=json_data['invoice_number']
    # print("Type of decoded_dict", type(json_data))
    return json_data
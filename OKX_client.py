from okx import OkxRestClient 

api_key = ""
secret_key = "3C4C731D630FE05F0D02C1281D3C3271"
Pass = "Haroon.51265"

client = OkxRestClient(api_key,secret_key,Pass,domain="https://www.okx.com/demo-trading")

order = client.trade()
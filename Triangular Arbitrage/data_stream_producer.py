from bs4 import BeautifulSoup 
from selenium import webdriver 
from selenium.webdriver.chrome.options import Options
import itertools
import json
import time
import boto3

region = "eu-west-1"
ssm_client = boto3.client('ssm', region_name=region)
currency = ssm_client.get_parameter(Name='currency')['Parameter']['Value']
kinesisDataStream = ssm_client.get_parameter(Name='kinesisDataStream')['Parameter']['Value']
kds_client = boto3.client('kinesis', region_name = region)
exchangeRates = []
line = {}

def triangular_composition():
    currencyList = list(forEXRates.keys())  
    currencyList.remove('BTC/USD')
    currencyList.remove('BTC/EUR')
    currencyList.remove('ETH/USD')
    n=3
    listCur = list(itertools.permutations(currencyList,n))
    return listCur

def filtering_function(a):
    if a[0].find(currency) !=-1 and a[-1].find(currency) !=-1 and a[1].find(currency)==-1 and\
        (a[1].find(a[0][:3]) !=-1 or a[1].find(a[0][4:7]) !=-1) and (a[-1].find(a[1][:3]) !=-1 or\
        a[-1].find(a[1][4:7]) !=-1):
        return True
    else:
        return False

url = 'https://www.investing.com/currencies/streaming-forex-rates-majors'
options = Options()
options.add_argument("--headless")
options.add_argument("window-size=1400,1500")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("start-maximized")
options.add_argument("enable-automation")
options.add_argument("--disable-infobars")
options.add_argument("--disable-dev-shm-usage") 

for h in range(10): # This can be made as an infinite cycle with 'while true'.
    exchangeRates = []
    driver = webdriver.Chrome('/usr/bin/chromedriver', options=options)
    driver.get(url)  
    # Make sure that the page is loaded
    time.sleep(2)  
    html = driver.page_source  
    soup = BeautifulSoup(html, "html.parser") 
    all_divs = soup.find("table", {"id": "cr1"}).find('tbody').find_all('tr') 

    # Get the currencies
    forEXRates = {}
    
    for i in all_divs: 
        cur = i.find("td", {"class": "bold left noWrap elp plusIconTd"}).text
        block = i.find_all('td') 
        bid = float(block[2].text.replace(",", ""))  
        ask = float(block[3].text.replace(",", ""))
        forEXRates[cur] = [bid, ask]
        
    # Extract the list of possible currency transactions for triangular arbitrage 
    if h == 0: 
        filteredList = list(filter(filtering_function, triangular_composition()))

    # Get the exchange rates for the filtered list    
    for p in filteredList:
        line[p[0]] = forEXRates[p[0]]
        line[p[1]] = forEXRates[p[1]]
        line[p[2]] = forEXRates[p[2]]
        exchangeRates.append(line)
        line = {}

    # Send data to Kinesis    
    response = kds_client.put_record(
        StreamName=kinesisDataStream,
        Data=json.dumps(exchangeRates),
        PartitionKey='tra'
    )
    
    print(exchangeRates)
 
    driver.close()

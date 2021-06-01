def calculate_arbitrage(event, context):

    import boto3
    import os
    from datetime import datetime
    from dateutil import tz
    import base64
    import json
    
    region = "eu-west-1"
    ssm_client = boto3.client('ssm', region_name=region)
    sns_client = boto3.client('sns', region_name=region)
    tz_London = tz.gettz("Europe/London")
    currency = ssm_client.get_parameter(Name='currency')['Parameter']['Value']
    investmentAmount = ssm_client.get_parameter(Name='investmentAmount')['Parameter']['Value']
    transactionCommission = ssm_client.get_parameter(Name='transactionCommission')['Parameter']['Value']
    records = event.get("Records")
    investmentAmount = float(investmentAmount)
    transactionCommission = float(transactionCommission)

    for record in records:
        Explanations = []
        Transactions = {"x":[0,0,0,0,0,0]}
        payload_b = base64.b64decode(record["kinesis"]["data"])
        payload = json.loads(payload_b)
        length_payload = len(payload)
        
        for fx in range(length_payload):
            item = payload[fx]   
            exchangeRatesKeys = list(item.keys())     
            firstTransactionBid = item[exchangeRatesKeys[0]][0]      
            firstTransactionAsk = item[exchangeRatesKeys[0]][1]
            firstTransactionCommission = investmentAmount * transactionCommission  
            firstShortTransactionAmount = investmentAmount - firstTransactionCommission    
            
            if exchangeRatesKeys[0].find(currency) == 0:
                firstLongTransactionAmount = firstShortTransactionAmount * firstTransactionBid      
                otex_1 = exchangeRatesKeys[0][4:7]      
                forex_1 = firstTransactionBid
            
            else:    
                firstLongTransactionAmount = firstShortTransactionAmount / firstTransactionAsk   
                otex_1 = exchangeRatesKeys[0][:3]   
                forex_1 = firstTransactionAsk     
            
            firstTransaction = f"Sell {currency} {investmentAmount:,.2f} and buy {otex_1} {firstLongTransactionAmount:,.2f} at the rate of {forex_1} and transaction cost of {currency} {firstTransactionCommission:,.2f}.   "    
            secondTransactionBid = item[exchangeRatesKeys[1]][0]
            secondTransactionAsk = item[exchangeRatesKeys[1]][1]
            secondTransactionCommission = firstLongTransactionAmount * transactionCommission
            secondShortTransactionAmount = firstLongTransactionAmount - secondTransactionCommission    
            
            if exchangeRatesKeys[1].find(otex_1) == 0:
                secondLongTransactionAmount = secondShortTransactionAmount * secondTransactionBid 
                otex_2 = exchangeRatesKeys[1][4:7]
                forex_2 = secondTransactionBid
            
            else:
                secondLongTransactionAmount = secondShortTransactionAmount / secondTransactionAsk
                otex_2 = exchangeRatesKeys[1][:3]
                forex_2 = secondTransactionAsk
            
            secondTransaction = f"Sell {otex_1} {secondShortTransactionAmount:,.2f} and buy {otex_2} {secondLongTransactionAmount:,.2f} at the rate of {forex_2} and transaction cost of {otex_1} {secondTransactionCommission:,.2f}.   " 
            thirdTransactionBid = item[exchangeRatesKeys[2]][0]
            thirdTransactionAsk = item[exchangeRatesKeys[2]][1]
            thirdTransactionCommission = secondLongTransactionAmount * transactionCommission
            thirdShortTransactionAmount = secondLongTransactionAmount - thirdTransactionCommission    
            
            if exchangeRatesKeys[2].find(otex_2) == 0:  
                thirdLongTransactionAmount = thirdShortTransactionAmount * thirdTransactionBid 
                otex_3 = exchangeRatesKeys[2][4:7]
                forex_3 = thirdTransactionBid
            
            else:
                thirdLongTransactionAmount = thirdShortTransactionAmount / thirdTransactionAsk
                otex_3 = exchangeRatesKeys[2][:3]
                forex_3 = thirdTransactionAsk
            
            thirdTransaction = f"Sell {otex_2} {thirdShortTransactionAmount:,.2f} and buy {otex_3} {thirdLongTransactionAmount:,.2f} at the rate of {forex_3} and transaction cost of {otex_2} {thirdTransactionCommission:,.2f}.   "
            profitOrLoss = thirdLongTransactionAmount - investmentAmount
            datetime_London = datetime.now(tz=tz_London)
            londonDateTime = datetime_London.strftime("%Y/%m/%d - %H:%M:%S")
            
            if profitOrLoss > 0 and profitOrLoss > Transactions["x"][4]:
                Transactions.clear()
                Explanations.extend([londonDateTime, firstTransaction, secondTransaction, thirdTransaction, profitOrLoss, thirdLongTransactionAmount])
                Transactions["x"] = Explanations

        if Transactions["x"][4] > 0:  
            netProfit = float(Transactions["x"][4])
            earnedAmount = float(Transactions["x"][5])
            message = f"London time: {Transactions['x'][0]} >>> There is an opportunity for triangular arbitrage to take advantage of.   * {Transactions['x'][1]} * {Transactions['x'][2]} * {Transactions['x'][3]} ** Invested {currency} {investmentAmount:,.2f} and earned {currency} {earnedAmount:,.2f} thus making {currency} {netProfit:,.2f} profit."
            response = sns_client.publish(
              TopicArn=os.environ['topicArn'],
              Message=json.dumps({'default': json.dumps(message)}),
              Subject='A triangular arbitrage opportunity',
              MessageStructure='json'
            )       
    
            print(message)
        
        else:
            no_trade_message = f"London time: {londonDateTime} >>> There is no occassion for triangular arbitrage."
            print(no_trade_message)
            

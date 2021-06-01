This program calculates loss or profit from triangular transactions among various global currencies. Rates are collected from <https://www.investing.com/currencies/streaming-forex-rates-majors>.

Those who want to know about what triangular arbitrage is may visit <https://www.investopedia.com/terms/t/triangulararbitrage.asp> to find out.

Triangular arbitrage is way of riskless trading taking advantage of momentary imbalances between the exchange rates. In real life, institutional investors engage in such transactions and those transactions are fulfilled by special software automatically in a second or so. This program obviously does not have that capacity but imitates the process and shows the use of AWS resources and some python libraries in performing that process.

AWS resources are deployed in the following manner:

<p align="center">
<img src="https://user-images.githubusercontent.com/40828825/120358740-864c3880-c30f-11eb-8e8e-47cc0efbff24.png"  />
</p>

`triangular_arbitrage.py` creates the necessary AWS resources. `data_stream_producer.py` scrapes the exchange rate page, collects the data and sends them over to Kinesis Data Stream. `lambda_function.py` analyzes the data and sends notification if a profitable opportunity exists.

When the program runs and a profitable transaction opportunity appears, it sends an email message similar to the below:

>"London time: 2021/01/28 - 14:07:37 >>> There is an opportunity for triangular arbitrage to take advantage of.   * Sell USD 1,000,000.00 and buy JPY 104,320,000.00 at the rate of 104.32 and transaction cost of USD 0.00.    * Sell JPY 104,320,000.00 and buy EUR 824,207.95 at the rate of 126.57 and transaction cost of JPY 0.00.    * Sell EUR 824,207.95 and buy USD 1,000,011.50 at the rate of 1.2133 and transaction cost of EUR 0.00.    ** Invested USD 1,000,000.00 and earned USD 1,000,011.50 thus making USD 11.50 profit."

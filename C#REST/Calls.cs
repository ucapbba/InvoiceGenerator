// See https://aka.ms/new-console-template for more information
using Newtonsoft.Json;
using RestSharp;
using System.Data;
using System.Text.Json.Nodes;

public class myRESTAPI
{
    public static bool success=false;
    public static string InvoiceGeneratorURI = "https://invoicegeneratorbea.azurewebsites.net/";
    public static string endpoint = "api/Todo/";
    public static List<InvoiceLine> Get()
    {
        var client = new RestClient(InvoiceGeneratorURI);
        var request = new RestRequest(endpoint, Method.Get);
        RestResponse queryResult = client.Execute(request);
        if (queryResult.Content != null)
        {
            if (queryResult.IsSuccessful)
            {
                success = true;
                var jsonObject = JsonConvert.DeserializeObject<List<InvoiceLine>>(queryResult.Content);
                return jsonObject;
            }
        }
        success = false;
        return new List<InvoiceLine>();
    }
    public static string? Post(int id,string itemName)
    {
        var client = new RestClient(InvoiceGeneratorURI);
        var request = new RestRequest(endpoint, Method.Post);
        request.RequestFormat = DataFormat.Json;
        InvoiceLine model = new InvoiceLine(id, itemName, "", 123, "", "", ""); //TODO 
        var dataString = JsonConvert.SerializeObject(model);
        request.AddStringBody(dataString, DataFormat.Json);
        RestResponse queryResult = client.Execute(request);
        return IsQuerySuccessful(queryResult);
    }

    public static string? delete(int id)
    {
        var client = new RestClient(InvoiceGeneratorURI);
        var request = new RestRequest(endpoint + id.ToString(), Method.Delete);
        RestResponse queryResult = client.Execute(request);
        return IsQuerySuccessful(queryResult);
    }

    public static string? IsQuerySuccessful(RestResponse queryResult)
    {
        if (queryResult.IsSuccessful)
        {
            success = true;
            return queryResult.Content;
        }
        else
        {
            success = false;
            return null;
        }
    }


}
public class InvoiceLine
{
    public InvoiceLine(int _id, string _date, string _name, double _amount, string _address, string _type, string _email)
    {
        id = _id;
        date = _date;
        name = _name;
        amount = _amount;
        address = _address;
        type = _type;
        email = _email;
    }
    [JsonProperty("id")]
    public int? id { get; set; } //needed for GET for not for POST
    [JsonProperty("date")]
    public string date { get; set; }
    [JsonProperty("name")]
    public string name { get; set; }
    [JsonProperty("amount")]
    public double amount { get; set; }
    [JsonProperty("address")]
    public string address { get; set; }
    [JsonProperty("type")]
    public string type { get; set; }
    [JsonProperty("email")]
    public string email { get; set; }


}
namespace InvoiceGenerator.Models
{
    public class InvoiceItem
    {
        public long Id { get; set; }
        public string Date { get; set; }
        public string Name { get; set; }
        public double Amount { get; set; }
        public string Address { get; set; }
        public string Type { get; set; }
        public string Email { get; set; }
    }
}
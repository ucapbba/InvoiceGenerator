using Microsoft.EntityFrameworkCore;

namespace InvoiceGenerator.Models
{
    public class InvoiceContext : DbContext
    {
        public InvoiceContext (DbContextOptions<InvoiceContext> options)
            : base(options)
        {
        }

        public DbSet<InvoiceItem> TodoItems { get; set; }
    }
}

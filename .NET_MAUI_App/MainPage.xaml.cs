using MauiApp1.ViewModel;
using System.Collections.ObjectModel;

namespace MauiApp1
{
    public partial class MainPage : ContentPage
    {
        public ObservableCollection<InvoiceLine> InvoiceCollection { get; set; }
        public MainPage(MainViewModel vm)
        {
            InitializeComponent();
            BindingContext = vm;
        }

     
    }
}
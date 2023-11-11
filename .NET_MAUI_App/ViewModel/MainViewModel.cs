using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace MauiApp1.ViewModel
{
    public partial class MainViewModel : ObservableObject
    {
        public string name { get; set; }
        public string date { get; set; }
        public double amount { get; set; }

        [ObservableProperty]
        public string total;
        public MainViewModel() 
        {
            Label totalLabel = new Label();
            totalLabel.BindingContext = this;
            totalLabel.SetBinding(Label.TextProperty, nameof(Total));
            ReloadFromServer();
        }
     
        public void ReloadFromServer()
        {
            List<InvoiceLine> currentItems = myRESTAPI.Get();
            int size = currentItems.Count;
            double sumTotal = 0;
            ObservableCollection<InvoiceLine> invoiceCollection = new ObservableCollection<InvoiceLine>();
            foreach (InvoiceLine item in currentItems)
            {
                sumTotal += item.amount;
                invoiceCollection.Add(item);
            }

            Total = "£ " + sumTotal.ToString();
            Items = invoiceCollection;
            OnPropertyChanged(nameof(Total));
            OnPropertyChanged(nameof(Items));
        }
        [ObservableProperty]
        ObservableCollection<InvoiceLine>   _items;

        [ObservableProperty]
        string text;

        [RelayCommand]
        void FilterByDate()
        {

            if (string.IsNullOrEmpty(Text))
            {
                ReloadFromServer(); //does not refresh
            }

            var filteredItems = Items.Where(e => e.date == Text);
            double sumTotal = 0;
            ObservableCollection<InvoiceLine> invoiceCollection = new ObservableCollection<InvoiceLine>();
            foreach (InvoiceLine item in filteredItems)
            {
                sumTotal += item.amount;
                invoiceCollection.Add(item);
            }
            Items = invoiceCollection;
            Total = "£ " + sumTotal.ToString();
            OnPropertyChanged(nameof(Total));
            OnPropertyChanged(nameof(Items));
            Text = string.Empty;
        }

    }
}

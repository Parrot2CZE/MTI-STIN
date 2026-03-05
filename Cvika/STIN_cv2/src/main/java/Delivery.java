public class Delivery {

    private final String trackingNumber;
    private final double weight;
    private final ShippingMethod shippingMethod;

    public Delivery(String trackingNumber, double weight, ShippingMethod shippingMethod) {
        this.trackingNumber = trackingNumber;
        this.weight = weight;
        this.shippingMethod = shippingMethod;
    }

    public String getTrackingNumber() {
        return trackingNumber;
    }

    public double getWeight() {
        return weight;
    }

    public ShippingMethod getShippingMethod() {
        return shippingMethod;
    }

    public double calculatePrice() {
       return shippingMethod.calculateCost(weight);
    }
}
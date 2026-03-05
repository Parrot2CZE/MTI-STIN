public class TruckDelivery implements ShippingMethod {

    private static final double BASE_PRICE = 100.0;
    private static final double PRICE_PER_KG = 10.0;

    @Override
    public double calculateCost(double weight) {
        return BASE_PRICE + PRICE_PER_KG * weight;
    }
}
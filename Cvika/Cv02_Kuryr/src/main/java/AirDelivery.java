public class AirDelivery implements ShippingMethod {

    private static final double BASE_PRICE = 300.0;
    private static final double PRICE_PER_KG = 25.0;

    @Override
    public double calculateCost(double weight) {
        return BASE_PRICE + PRICE_PER_KG * weight;
    }
}
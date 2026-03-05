public class BikeDelivery implements ShippingMethod {

    private static final double FIXED_PRICE = 80.0;
    private static final double MAX_WEIGHT = 5.0;

    @Override
    public double calculateCost(double weight) {
        if (weight > MAX_WEIGHT) {
            throw new java.lang.IllegalArgumentException(
                    "Bike delivery is only available for packages up to "
                            + MAX_WEIGHT + " kg. Given weight: " + weight
            );
        }
        return FIXED_PRICE;
    }
}
using UnityEngine;

public class TrainingPickup : MonoBehaviour
{
    public enum PickupType { Health, Ammo, Grenade }

    public PickupType type = PickupType.Health;
    public float healAmount = 35f;
    public int pistolAmmo = 18;
    public int rifleAmmo = 45;
    public int gatlingAmmo = 60;
    public int grenades = 1;
    public float spinSpeed = 70f;
    public float bobHeight = 0.18f;
    public float bobSpeed = 2.2f;

    private Vector3 startPosition;

    void Start()
    {
        startPosition = transform.position;
    }

    void Update()
    {
        transform.Rotate(Vector3.up, spinSpeed * Time.deltaTime, Space.World);
        transform.position = startPosition + Vector3.up * (Mathf.Sin(Time.time * bobSpeed) * bobHeight);
    }

    void OnTriggerEnter(Collider other)
    {
        PlayerHealth health = other.GetComponent<PlayerHealth>();
        if (health == null)
            health = other.GetComponentInParent<PlayerHealth>();

        if (health == null)
            return;

        WeaponController weapons = Object.FindFirstObjectByType<WeaponController>();

        if (type == PickupType.Health)
            health.Heal(healAmount);
        else if (type == PickupType.Ammo && weapons != null)
            weapons.AddAmmo(pistolAmmo, rifleAmmo, gatlingAmmo);
        else if (type == PickupType.Grenade && weapons != null)
            weapons.AddGrenades(grenades);

        SpawnCollectFx();
        Destroy(gameObject);
    }

    private void SpawnCollectFx()
    {
        for (int i = 0; i < 5; i++)
        {
            GameObject fx = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            Destroy(fx.GetComponent<Collider>());
            fx.transform.position = transform.position + Random.insideUnitSphere * 0.35f;
            fx.transform.localScale = Vector3.one * 0.12f;

            Renderer renderer = fx.GetComponent<Renderer>();
            if (renderer != null)
                renderer.material.color = GetColor();

            Destroy(fx, 0.45f);
        }
    }

    public Color GetColor()
    {
        if (type == PickupType.Health)
            return new Color(0.18f, 0.9f, 0.35f);
        if (type == PickupType.Ammo)
            return new Color(0.95f, 0.78f, 0.2f);
        return new Color(0.35f, 0.8f, 1f);
    }
}

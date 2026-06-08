using UnityEngine;

public class Grenade : MonoBehaviour
{
    private float radius;
    private float damage;
    private AudioClip explosionClip;

    public void Init(float fuse, float radius, float damage, AudioClip clip)
    {
        this.radius = radius;
        this.damage = damage;
        explosionClip = clip;
        Invoke(nameof(Explode), fuse);
    }

    private void Explode()
    {
        if (explosionClip != null)
            AudioSource.PlayClipAtPoint(explosionClip, transform.position);

        SpawnEffect();

        Collider[] hits = Physics.OverlapSphere(transform.position, radius);
        foreach (Collider hit in hits)
        {
            float distance = Vector3.Distance(transform.position, hit.transform.position);
            float falloff = Mathf.Clamp01(1f - distance / radius);

            EnemyHealth enemy = hit.GetComponent<EnemyHealth>();
            if (enemy == null)
                enemy = hit.GetComponentInParent<EnemyHealth>();
            if (enemy != null)
                enemy.TakeDamage(damage * falloff);

            PlayerHealth player = hit.GetComponent<PlayerHealth>();
            if (player == null)
                player = hit.GetComponentInParent<PlayerHealth>();
            if (player != null)
                player.TakeDamage(damage * 0.5f * falloff);
        }

        Destroy(gameObject);
    }

    private void SpawnEffect()
    {
        GameObject fx = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        Destroy(fx.GetComponent<Collider>());
        fx.transform.position = transform.position;

        Renderer renderer = fx.GetComponent<Renderer>();
        if (renderer != null)
            renderer.material.color = new Color(1f, 0.55f, 0.1f);

        fx.AddComponent<ExplosionFx>().Init(radius);
    }
}

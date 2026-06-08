using UnityEngine;

public class EnemyHealth : MonoBehaviour
{
    public float health = 50f;

    private bool dead;
    private Renderer rend;
    private Color baseColor;
    private float flashTimer;

    void Start()
    {
        rend = GetComponentInChildren<Renderer>();
        if (rend != null)
            baseColor = rend.material.color;
    }

    void Update()
    {
        if (flashTimer > 0f)
        {
            flashTimer -= Time.deltaTime;
            if (flashTimer <= 0f && rend != null)
                rend.material.color = baseColor;
        }
    }

    public void TakeDamage(float amount)
    {
        if (dead) return;
        health -= amount;
        Flash();
        if (health <= 0f)
            Die();
    }

    private void Flash()
    {
        if (rend == null) return;
        rend.material.color = Color.white;
        flashTimer = 0.06f;
    }

    private void Die()
    {
        dead = true;
        SpawnDeathFx();
        if (GameManager.Instance != null)
            GameManager.Instance.AddKill();
        Destroy(gameObject);
    }

    private void SpawnDeathFx()
    {
        for (int i = 0; i < 6; i++)
        {
            GameObject piece = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            Destroy(piece.GetComponent<Collider>());
            piece.transform.position = transform.position + Vector3.up;
            piece.transform.localScale = Vector3.one * 0.25f;

            Renderer pieceRenderer = piece.GetComponent<Renderer>();
            if (pieceRenderer != null)
                pieceRenderer.material.color = new Color(1f, 0.5f, 0.1f);

            Rigidbody rb = piece.AddComponent<Rigidbody>();
            rb.linearVelocity = new Vector3(Random.Range(-3f, 3f), Random.Range(2f, 5f), Random.Range(-3f, 3f));
            Destroy(piece, 0.8f);
        }
    }
}

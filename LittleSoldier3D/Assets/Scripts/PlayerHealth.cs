using UnityEngine;

public class PlayerHealth : MonoBehaviour
{
    public float maxHealth = 150f;
    public float currentHealth;
    public float spawnProtectionTime = 4f;
    public float damageCooldown = 0.65f;
    public float regenDelay = 5f;
    public float regenPerSecond = 10f;
    public float lowHealthRegenLimit = 75f;

    public float LastDamageTime { get; private set; }
    public float LastHealTime { get; private set; }
    public bool IsProtected { get { return Time.time < protectedUntil; } }

    private bool dead;
    private float protectedUntil;

    void OnEnable()
    {
        dead = false;
        currentHealth = maxHealth;
        LastDamageTime = -999f;
        LastHealTime = -999f;
        protectedUntil = Time.time + spawnProtectionTime;
    }

    void Start()
    {
        dead = false;
        currentHealth = maxHealth;
        LastDamageTime = -999f;
        LastHealTime = -999f;
        protectedUntil = Time.time + spawnProtectionTime;
    }

    void Update()
    {
        if (dead || currentHealth <= 0f)
            return;

        if (Time.time - LastDamageTime < regenDelay)
            return;

        if (currentHealth < Mathf.Min(maxHealth, lowHealthRegenLimit))
            Heal(regenPerSecond * Time.deltaTime);
    }

    public void TakeDamage(float amount)
    {
        if (dead) return;
        if (IsProtected) return;
        if (Time.time - LastDamageTime < damageCooldown) return;

        currentHealth -= amount;
        LastDamageTime = Time.time;
        if (currentHealth <= 0f)
        {
            currentHealth = 0f;
            Die();
        }
    }

    void Die()
    {
        dead = true;
        if (GameManager.Instance != null)
            GameManager.Instance.PlayerDied();
    }

    public void Heal(float amount)
    {
        if (dead || amount <= 0f)
            return;

        currentHealth = Mathf.Min(maxHealth, currentHealth + amount);
        LastHealTime = Time.time;
    }

    public float Current { get { return currentHealth; } }
    public float Max { get { return maxHealth; } }
}

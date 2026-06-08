using System.Collections;
using UnityEngine;

[System.Serializable]
public class Weapon
{
    public string name = "\u624b\u67aa";
    public float damage = 25f;
    public float fireRate = 3f;
    public int magazineSize = 12;
    public int reserveAmmo = 48;
    public float reloadTime = 1.1f;
    public float spread = 0.005f;
    public float recoil = 1.2f;
    public bool automatic = false;
    public float range = 100f;
    [HideInInspector] public int currentInMag;
}

public class WeaponController : MonoBehaviour
{
    public Weapon[] weapons;

    [Header("Grenade")]
    public int grenadeCount = 3;
    public float grenadeDamage = 80f;
    public float grenadeRadius = 6f;
    public float grenadeFuse = 2.2f;
    public float grenadeThrowForce = 14f;

    [Header("Optional Audio")]
    public AudioClip shootClip;
    public AudioClip reloadClip;
    public AudioClip emptyClip;
    public AudioClip explosionClip;

    [Header("Weapon View")]
    public WeaponView weaponView;

    private int index = 0;
    private bool grenadeSelected = false;
    private bool reloading = false;
    private float nextFireTime = 0f;

    private MouseLook mouseLook;
    private AudioSource audioSource;

    public float LastShotTime { get; private set; }
    public float LastHitTime { get; private set; }

    void Start()
    {
        mouseLook = GetComponent<MouseLook>();
        audioSource = GetComponent<AudioSource>();
        if (weaponView == null)
            weaponView = GetComponent<WeaponView>();

        if (weapons != null)
        {
            foreach (Weapon weapon in weapons)
                weapon.currentInMag = weapon.magazineSize;
        }

        index = 0;
        grenadeSelected = false;
        UpdateWeaponView();
    }

    void Update()
    {
        if (GameManager.Instance != null &&
            GameManager.Instance.CurrentState != GameManager.State.Playing)
            return;

        if (weapons == null || weapons.Length == 0)
            return;

        HandleSwitch();
        HandleReload();
        HandleFire();
    }

    private void HandleSwitch()
    {
        if (Input.GetKeyDown(KeyCode.Alpha1)) Select(0);
        if (Input.GetKeyDown(KeyCode.Alpha2)) Select(1);
        if (Input.GetKeyDown(KeyCode.Alpha3)) Select(2);
        if (Input.GetKeyDown(KeyCode.Alpha4)) SelectGrenade();
    }

    private void Select(int weaponIndex)
    {
        if (weaponIndex >= weapons.Length)
            return;

        StopAllCoroutines();
        reloading = false;
        index = weaponIndex;
        grenadeSelected = false;
        UpdateWeaponView();
    }

    private void SelectGrenade()
    {
        StopAllCoroutines();
        reloading = false;
        grenadeSelected = true;
        UpdateWeaponView();
    }

    private void HandleReload()
    {
        if (grenadeSelected || reloading)
            return;

        Weapon weapon = weapons[index];
        if (Input.GetKeyDown(KeyCode.R) && weapon.currentInMag < weapon.magazineSize && weapon.reserveAmmo > 0)
            StartCoroutine(Reload(weapon));
    }

    private IEnumerator Reload(Weapon weapon)
    {
        reloading = true;
        if (reloadClip != null && audioSource != null)
            audioSource.PlayOneShot(reloadClip);
        if (weaponView != null)
            weaponView.PlayReload(weapon.reloadTime);

        yield return new WaitForSeconds(weapon.reloadTime);

        int need = weapon.magazineSize - weapon.currentInMag;
        int take = Mathf.Min(need, weapon.reserveAmmo);
        weapon.currentInMag += take;
        weapon.reserveAmmo -= take;
        reloading = false;
    }

    private void HandleFire()
    {
        if (grenadeSelected)
        {
            if (Input.GetMouseButtonDown(0))
                ThrowGrenade();
            return;
        }

        Weapon weapon = weapons[index];
        if (reloading)
            return;

        bool wantFire = weapon.automatic ? Input.GetMouseButton(0) : Input.GetMouseButtonDown(0);
        if (!wantFire || Time.time < nextFireTime)
            return;

        if (weapon.currentInMag <= 0)
        {
            if (Input.GetMouseButtonDown(0) && emptyClip != null && audioSource != null)
                audioSource.PlayOneShot(emptyClip);

            nextFireTime = Time.time + 0.2f;
            return;
        }

        Fire(weapon);
        nextFireTime = Time.time + 1f / Mathf.Max(0.01f, weapon.fireRate);
    }

    private void Fire(Weapon weapon)
    {
        weapon.currentInMag--;
        LastShotTime = Time.time;
        if (shootClip != null && audioSource != null)
            audioSource.PlayOneShot(shootClip);

        if (mouseLook != null)
            mouseLook.AddRecoil(weapon.recoil);
        if (weaponView != null)
            weaponView.PlayFire(weapon.recoil);
        SpawnMuzzleFx();

        Vector3 direction = transform.forward
            + transform.right * Random.Range(-weapon.spread, weapon.spread)
            + transform.up * Random.Range(-weapon.spread, weapon.spread);

        if (Physics.Raycast(transform.position, direction.normalized, out RaycastHit hit, weapon.range))
        {
            EnemyHealth enemy = hit.transform.GetComponent<EnemyHealth>();
            if (enemy == null)
                enemy = hit.transform.GetComponentInParent<EnemyHealth>();
            if (enemy != null)
            {
                enemy.TakeDamage(weapon.damage);
                LastHitTime = Time.time;
                SpawnHitFx(hit.point);
            }

            Target target = hit.transform.GetComponent<Target>();
            if (target != null)
                target.TakeDamage(weapon.damage);
        }
    }

    private void ThrowGrenade()
    {
        if (grenadeCount <= 0)
            return;

        grenadeCount--;
        if (weaponView != null)
            weaponView.PlayFire(0.5f);

        GameObject grenade = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        grenade.transform.localScale = Vector3.one * 0.3f;
        grenade.transform.position = transform.position + transform.forward * 1f;

        Renderer renderer = grenade.GetComponent<Renderer>();
        if (renderer != null)
            renderer.material.color = new Color(0.18f, 0.28f, 0.15f);

        Rigidbody rb = grenade.AddComponent<Rigidbody>();
        rb.linearVelocity = transform.forward * grenadeThrowForce + Vector3.up * 2f;

        Grenade grenadeScript = grenade.AddComponent<Grenade>();
        grenadeScript.Init(grenadeFuse, grenadeRadius, grenadeDamage, explosionClip);
    }

    private void SpawnHitFx(Vector3 position)
    {
        GameObject fx = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        Destroy(fx.GetComponent<Collider>());
        fx.transform.position = position;
        fx.transform.localScale = Vector3.one * 0.15f;

        Renderer renderer = fx.GetComponent<Renderer>();
        if (renderer != null)
            renderer.material.color = new Color(1f, 0.9f, 0.4f);

        Destroy(fx, 0.08f);
    }

    private void SpawnMuzzleFx()
    {
        GameObject fx = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        Destroy(fx.GetComponent<Collider>());
        fx.transform.SetParent(transform, false);
        fx.transform.localPosition = new Vector3(0.32f, -0.18f, 0.95f);
        fx.transform.localScale = Vector3.one * 0.16f;

        Renderer renderer = fx.GetComponent<Renderer>();
        if (renderer != null)
            renderer.material.color = new Color(1f, 0.76f, 0.18f);

        Destroy(fx, 0.05f);
    }

    public void AddAmmo(int pistolAmmo, int rifleAmmo, int gatlingAmmo)
    {
        if (weapons == null)
            return;

        if (weapons.Length > 0)
            weapons[0].reserveAmmo += pistolAmmo;
        if (weapons.Length > 1)
            weapons[1].reserveAmmo += rifleAmmo;
        if (weapons.Length > 2)
            weapons[2].reserveAmmo += gatlingAmmo;
    }

    public void AddGrenades(int amount)
    {
        grenadeCount += Mathf.Max(0, amount);
    }

    private void UpdateWeaponView()
    {
        if (weaponView != null)
            weaponView.SetWeapon(index, grenadeSelected);
    }

    public string CurrentWeaponName { get { return grenadeSelected ? "\u624b\u96f7" : weapons[index].name; } }
    public int CurrentMag { get { return grenadeSelected ? 0 : weapons[index].currentInMag; } }
    public int CurrentReserve { get { return grenadeSelected ? 0 : weapons[index].reserveAmmo; } }
    public bool IsGrenadeSelected { get { return grenadeSelected; } }
    public int GrenadeCount { get { return grenadeCount; } }
    public bool IsReloading { get { return reloading; } }
}

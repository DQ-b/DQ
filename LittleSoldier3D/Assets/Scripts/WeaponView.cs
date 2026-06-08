using System.Collections;
using UnityEngine;

public class WeaponView : MonoBehaviour
{
    public Transform weaponRoot;
    public GameObject[] weaponModels;

    public Vector3 baseLocalPosition = new Vector3(0.34f, -0.32f, 0.58f);
    public Vector3 baseLocalEuler = new Vector3(0f, 0f, 0f);
    public float swayAmount = 0.014f;
    public float bobAmount = 0.016f;
    public float returnSpeed = 12f;

    private Vector3 positionVelocity;
    private float recoilKick;
    private float reloadTilt;
    private Coroutine reloadRoutine;

    void Awake()
    {
        if (weaponRoot == null || weaponModels == null || weaponModels.Length == 0)
            BuildDefaultViewModels();
    }

    void Update()
    {
        if (weaponRoot == null)
            return;

        float mouseX = Input.GetAxisRaw("Mouse X");
        float mouseY = Input.GetAxisRaw("Mouse Y");
        bool moving = Mathf.Abs(Input.GetAxisRaw("Horizontal")) + Mathf.Abs(Input.GetAxisRaw("Vertical")) > 0.1f;

        Vector3 targetPosition = baseLocalPosition;
        targetPosition.x += Mathf.Clamp(-mouseX * swayAmount, -0.045f, 0.045f);
        targetPosition.y += Mathf.Clamp(-mouseY * swayAmount, -0.04f, 0.04f);
        targetPosition.z -= recoilKick;

        if (moving)
        {
            float bob = Mathf.Sin(Time.time * 9f) * bobAmount;
            targetPosition.y += bob;
            targetPosition.x += Mathf.Cos(Time.time * 9f) * bobAmount * 0.35f;
        }

        weaponRoot.localPosition = Vector3.SmoothDamp(
            weaponRoot.localPosition,
            targetPosition,
            ref positionVelocity,
            1f / Mathf.Max(1f, returnSpeed));

        Vector3 targetEuler = baseLocalEuler;
        targetEuler.x += recoilKick * 18f + Mathf.Clamp(mouseY * 1.1f, -4f, 4f);
        targetEuler.y += Mathf.Clamp(-mouseX * 1.35f, -6f, 6f);
        targetEuler.z += reloadTilt;

        weaponRoot.localRotation = Quaternion.Slerp(
            weaponRoot.localRotation,
            Quaternion.Euler(targetEuler),
            Time.deltaTime * returnSpeed);

        recoilKick = Mathf.MoveTowards(recoilKick, 0f, Time.deltaTime * 0.75f);
    }

    public void BuildDefaultViewModels()
    {
        Transform existing = transform.Find("FirstPersonWeapon");
        if (existing != null)
            SafeDestroy(existing.gameObject);

        GameObject root = new GameObject("FirstPersonWeapon");
        weaponRoot = root.transform;
        weaponRoot.SetParent(transform, false);
        weaponRoot.localPosition = baseLocalPosition;
        weaponRoot.localRotation = Quaternion.Euler(baseLocalEuler);
        weaponRoot.localScale = Vector3.one;

        weaponModels = new GameObject[4];
        weaponModels[0] = BuildPistol(weaponRoot);
        weaponModels[1] = BuildRifle(weaponRoot);
        weaponModels[2] = BuildGatling(weaponRoot);
        weaponModels[3] = BuildGrenade(weaponRoot);

        SetWeapon(0, false);
    }

    public void SetWeapon(int weaponIndex, bool grenadeSelected)
    {
        if (weaponModels == null || weaponModels.Length == 0)
            return;

        int showIndex = grenadeSelected ? weaponModels.Length - 1 : Mathf.Clamp(weaponIndex, 0, weaponModels.Length - 2);
        for (int i = 0; i < weaponModels.Length; i++)
        {
            if (weaponModels[i] != null)
                weaponModels[i].SetActive(i == showIndex);
        }

        recoilKick = 0f;
    }

    public void PlayFire(float strength)
    {
        recoilKick = Mathf.Clamp(recoilKick + Mathf.Lerp(0.035f, 0.09f, Mathf.Clamp01(strength / 2f)), 0f, 0.14f);
    }

    public void PlayReload(float duration)
    {
        if (!isActiveAndEnabled)
            return;

        if (reloadRoutine != null)
            StopCoroutine(reloadRoutine);

        reloadRoutine = StartCoroutine(ReloadTilt(duration));
    }

    private IEnumerator ReloadTilt(float duration)
    {
        float elapsed = 0f;
        duration = Mathf.Max(0.1f, duration);

        while (elapsed < duration)
        {
            float p = elapsed / duration;
            reloadTilt = Mathf.Sin(p * Mathf.PI) * -22f;
            elapsed += Time.deltaTime;
            yield return null;
        }

        reloadTilt = 0f;
        reloadRoutine = null;
    }

    private GameObject BuildPistol(Transform parent)
    {
        GameObject model = CreateModelRoot(parent, "View_Pistol");
        CreatePart(model.transform, PrimitiveType.Cube, "Slide", new Vector3(0f, 0.075f, 0.07f), new Vector3(0.2f, 0.075f, 0.38f), new Color(0.18f, 0.19f, 0.2f), Vector3.zero);
        CreatePart(model.transform, PrimitiveType.Cube, "Frame", new Vector3(0f, 0f, 0.02f), new Vector3(0.17f, 0.1f, 0.28f), new Color(0.08f, 0.09f, 0.1f), Vector3.zero);
        CreatePart(model.transform, PrimitiveType.Cylinder, "Barrel", new Vector3(0f, 0.075f, 0.32f), new Vector3(0.033f, 0.17f, 0.033f), new Color(0.02f, 0.02f, 0.025f), new Vector3(90f, 0f, 0f));
        CreatePart(model.transform, PrimitiveType.Cube, "Grip", new Vector3(0f, -0.15f, -0.07f), new Vector3(0.13f, 0.24f, 0.1f), new Color(0.07f, 0.075f, 0.08f), new Vector3(-12f, 0f, 0f));
        CreatePart(model.transform, PrimitiveType.Cube, "Trigger", new Vector3(0f, -0.07f, 0.05f), new Vector3(0.035f, 0.08f, 0.025f), new Color(0.01f, 0.01f, 0.012f), Vector3.zero);
        return model;
    }

    private GameObject BuildRifle(Transform parent)
    {
        GameObject model = CreateModelRoot(parent, "View_Rifle");
        CreatePart(model.transform, PrimitiveType.Cube, "Receiver", new Vector3(0f, 0.02f, 0.08f), new Vector3(0.22f, 0.13f, 0.5f), new Color(0.12f, 0.15f, 0.14f), Vector3.zero);
        CreatePart(model.transform, PrimitiveType.Cube, "Stock", new Vector3(0f, 0f, -0.34f), new Vector3(0.24f, 0.15f, 0.28f), new Color(0.09f, 0.1f, 0.095f), Vector3.zero);
        CreatePart(model.transform, PrimitiveType.Cylinder, "LongBarrel", new Vector3(0f, 0.055f, 0.55f), new Vector3(0.032f, 0.36f, 0.032f), new Color(0.025f, 0.027f, 0.03f), new Vector3(90f, 0f, 0f));
        CreatePart(model.transform, PrimitiveType.Cube, "Magazine", new Vector3(0f, -0.2f, 0.08f), new Vector3(0.12f, 0.24f, 0.11f), new Color(0.06f, 0.07f, 0.065f), new Vector3(7f, 0f, 0f));
        CreatePart(model.transform, PrimitiveType.Cube, "Grip", new Vector3(0f, -0.18f, -0.16f), new Vector3(0.12f, 0.22f, 0.1f), new Color(0.05f, 0.06f, 0.055f), new Vector3(-15f, 0f, 0f));
        CreatePart(model.transform, PrimitiveType.Cube, "Sight", new Vector3(0f, 0.13f, 0.14f), new Vector3(0.12f, 0.04f, 0.25f), new Color(0.02f, 0.025f, 0.025f), Vector3.zero);
        return model;
    }

    private GameObject BuildGatling(Transform parent)
    {
        GameObject model = CreateModelRoot(parent, "View_Gatling");
        CreatePart(model.transform, PrimitiveType.Cube, "MotorBody", new Vector3(0f, 0f, 0.02f), new Vector3(0.28f, 0.18f, 0.32f), new Color(0.15f, 0.15f, 0.16f), Vector3.zero);
        CreatePart(model.transform, PrimitiveType.Cylinder, "AmmoDrum", new Vector3(0f, -0.03f, -0.16f), new Vector3(0.15f, 0.08f, 0.15f), new Color(0.09f, 0.1f, 0.11f), new Vector3(0f, 0f, 90f));
        CreatePart(model.transform, PrimitiveType.Cube, "RearHandle", new Vector3(0f, -0.17f, -0.08f), new Vector3(0.16f, 0.24f, 0.08f), new Color(0.035f, 0.04f, 0.04f), new Vector3(-10f, 0f, 0f));

        float radius = 0.055f;
        for (int i = 0; i < 6; i++)
        {
            float angle = i * Mathf.PI * 2f / 6f;
            Vector3 offset = new Vector3(Mathf.Cos(angle) * radius, 0.075f + Mathf.Sin(angle) * radius, 0.46f);
            CreatePart(model.transform, PrimitiveType.Cylinder, "RotatingBarrel_" + i, offset, new Vector3(0.017f, 0.38f, 0.017f), new Color(0.025f, 0.027f, 0.03f), new Vector3(90f, 0f, 0f));
        }

        return model;
    }

    private GameObject BuildGrenade(Transform parent)
    {
        GameObject model = CreateModelRoot(parent, "View_Grenade");
        CreatePart(model.transform, PrimitiveType.Sphere, "GrenadeBody", new Vector3(0f, -0.03f, 0.05f), new Vector3(0.22f, 0.26f, 0.22f), new Color(0.14f, 0.22f, 0.12f), Vector3.zero);
        CreatePart(model.transform, PrimitiveType.Cube, "GrenadeCap", new Vector3(0f, 0.14f, 0.05f), new Vector3(0.12f, 0.05f, 0.1f), new Color(0.05f, 0.055f, 0.05f), Vector3.zero);
        CreatePart(model.transform, PrimitiveType.Cube, "GrenadePin", new Vector3(0.08f, 0.17f, 0.05f), new Vector3(0.08f, 0.015f, 0.07f), new Color(0.72f, 0.66f, 0.38f), Vector3.zero);
        return model;
    }

    private GameObject CreateModelRoot(Transform parent, string name)
    {
        GameObject model = new GameObject(name);
        model.transform.SetParent(parent, false);
        model.transform.localPosition = Vector3.zero;
        model.transform.localRotation = Quaternion.identity;
        model.transform.localScale = Vector3.one;
        return model;
    }

    private GameObject CreatePart(Transform parent, PrimitiveType type, string name, Vector3 position, Vector3 scale, Color color, Vector3 euler)
    {
        GameObject part = GameObject.CreatePrimitive(type);
        part.name = name;
        part.transform.SetParent(parent, false);
        part.transform.localPosition = position;
        part.transform.localRotation = Quaternion.Euler(euler);
        part.transform.localScale = scale;

        Collider collider = part.GetComponent<Collider>();
        if (collider != null)
            SafeDestroy(collider);

        Renderer renderer = part.GetComponent<Renderer>();
        if (renderer != null)
            renderer.sharedMaterial = CreateMaterial(color);

        return part;
    }

    private Material CreateMaterial(Color color)
    {
        Shader shader = Shader.Find("Universal Render Pipeline/Lit");
        if (shader == null)
            shader = Shader.Find("Standard");

        Material material = new Material(shader);
        material.color = color;
        return material;
    }

    private void SafeDestroy(Object target)
    {
        if (target == null)
            return;

        if (Application.isPlaying)
            Destroy(target);
        else
            DestroyImmediate(target);
    }
}
